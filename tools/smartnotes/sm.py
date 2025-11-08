#!/usr/bin/env python3
"""
Bible Study CLI — cost-efficient version with RAG‑lite selection, token/price guards, and dry-run.

Key features added:
- TF‑IDF top‑K chunk selection from Markdown notes
- Chunking by headings/paragraphs with configurable size
- Token counting via tiktoken; hard caps on context tokens
- Budget guard: abort if estimated cost exceeds --max-price
- Dry run: show selected chunks, token counts, and price without calling API
- Optional response caching keyed by model + instructions + question + chunk IDs

Usage examples:
  # Cheapest path: pick top 6 chunks and cap context tokens
  python bible_cli.py \
    --dir ./notes --recursive \
    --instructions ./instr.md \
    --question "How does James 2:14–26 relate to Romans 4?" \
    --top-k 6 --max-context-tokens 6000 --max-tokens 600

  # Dry run to see cost estimate without sending anything
  python bible_cli.py \
    --dir ./notes \
    --instructions ./instr.md \
    --question "Trace John's purpose statement" \
    --dry-run --top-k 8

  # Enforce budget ceiling
  python bible_cli.py \
    --note path/to/note.md \
    --instructions ./instr.md \
    --question "Summarize cross-references" \
    --max-price 0.10
    

  # MODEL_PRICES is now loaded from an external JSON file, defaulting to ~/.smart_notes_model_prices.json.
  # You can override the location with the environment variable SMART_NOTES_MODEL_PRICES.
  # Example file content:
  ```json
  {
    "gpt-5.1": { "in": 0.005, "out": 0.015 },
    "gpt-4o-mini": { "in": 0.15, "out": 0.60 }
  }
  ```
"""


# TODO: Should I change the format of my OpenAI API prompts and adjust how the `messages` list is built? 
# {
#   "role": "system",
#   "content": "Context:\nYou are assisting a biblical knowledge worker in analyzing and improving a collection of interconnected notes written in Markdown. Each note represents a single theological or doctrinal idea (\"atomic note\") and may contain references to Bible verses (formatted as Obsidian-style wikilinks) and links to other notes in the collection. One note serves as a Map of Content (MOC), organizing other notes under thematic or logical categories. The goal is to refine the knowledge base for clarity, organization, and usefulness by ensuring that each note is atomic, well-connected, non-redundant, and contributes to a coherent overall structure.\n\nRole:\nYou are an expert in knowledge management and digital note-taking systems, with two decades of experience in the Zettelkasten method, atomic note theory, and personal knowledge graph design. You are also proficient in theological studies and understand how to work with religious texts and doctrinal content. Your expertise lies in transforming scattered notes into a structured, non-redundant, and highly navigable knowledge base that fosters deep understanding and insight.\n\nAction:\n1. Identify the MOC note and assess how well it organizes related notes into logical groupings and progression.\n2. Suggest improvements to the MOC structure, such as reordering, splitting, merging, or renaming categories for clarity or conceptual flow.\n3. Review each note to ensure it focuses on a single atomic theological idea.\n4. Suggest any necessary splits, combinations, or rewording of notes to enhance atomicity and remove duplication.\n5. Analyze inter-note links and Bible verse connections:\n   a. Suggest missing links to relevant notes or concepts not yet referenced.\n   b. Identify redundant or weak links that could be removed or clarified.\n   c. Highlight verses that may be better explained or better placed.\n6. Recommend improvements to the internal linking strategy using Obsidian wikilinks—ensuring that each note maximally benefits from note-to-note and verse-to-note associations.\n7. Provide the output in clearly separated sections:\n   - “MOC Structure Suggestions”\n   - “Note Atomicity and Duplication Suggestions”\n   - “Connection Improvements (Notes + Verses)”\n\nFormat:\nPlain text output divided into clearly labeled sections. Use numbered or bulleted lists for clarity. Each note should be referred to by its filename or top-level heading. Maintain original Obsidian-style linking format (e.g., [[Romans 5#Romans 5 8|Romans 5:8]], [[Jesus’ death was atonement for sin]]). Do not alter any theological content—focus solely on structure and organization.\n\nTarget Audience:\nThe target audience includes digital theology researchers, pastors, and advanced Bible students using Obsidian or similar tools to study Scripture and doctrine. They value clear, logical, and efficient knowledge structures to support deep study and long-term insight. They are technically capable and already familiar with note-taking methodologies and biblical scholarship."
# }
# This JSON object is ready for inclusion in the messages array like so:

# json
# Copy code
# "messages": [
#   {
#     "role": "system",
#     "content": "..."
#   },
#   {
#     "role": "user",
#     "content": "..."
#   }
# ]
#

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pprint as pp
import re
import sys
import textwrap
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Tuple

try:
    from openai import OpenAI
except ImportError as e:
    sys.stderr.write("ERROR: openai package not installed. Run: pip install openai\n")
    raise

# Optional dependencies
try:
    import tiktoken  # pip install tiktoken
except Exception:
    tiktoken = None

FRONT_MATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

MODEL_PRICES_FILE = Path(os.environ.get("SMART_NOTES_MODEL_PRICES", Path.home() / ".smart_notes_model_prices.json"))


def load_model_prices() -> dict:
    if MODEL_PRICES_FILE.exists():
        try:
            with MODEL_PRICES_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            sys.stderr.write(f"Warning: could not parse {MODEL_PRICES_FILE}: {e}\n")
    return {}


MODEL_PRICES = load_model_prices()

# ---------------- Files ----------------

def read_markdown_file(path: Path, strip_front_matter: bool = True) -> str:
    text = path.read_text(encoding="utf-8")
    if strip_front_matter:
        text = FRONT_MATTER_RE.sub("", text, count=1)
    return text.strip()

def gather_notes(notes: Iterable[Path], dirs: Iterable[Path], recursive: bool) -> List[Path]:
    files: List[Path] = []
    for p in notes:
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Note not found or not a file: {p}")
        if p.suffix.lower() not in {".md", ".markdown"}:
            raise ValueError(f"Note must be Markdown: {p}")
        files.append(p)
    for d in dirs:
        if not d.exists() or not d.is_dir():
            raise NotADirectoryError(f"Not a directory: {d}")
        globber = d.rglob("*.md") if recursive else d.glob("*.md")
        files.extend(sorted(globber))
    # Deduplicate while preserving order
    seen = set()
    unique: List[Path] = []
    for f in files:
        rp = f.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(f)
    if not unique:
        raise FileNotFoundError("No Markdown notes found.")
    return unique

def gather_instructions(instruction_paths: Iterable[Path]) -> str:
    if not instruction_paths:
        return default_system_instructions().strip()
    chunks = []
    for p in instruction_paths:
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"Instruction file not found: {p}")
        if p.suffix.lower() not in {".md", ".markdown"}:
            raise ValueError(f"Instruction must be Markdown: {p}")
        chunks.append(read_markdown_file(p, strip_front_matter=False))
    return "\n\n".join(chunks).strip()

def default_system_instructions() -> str:
    return textwrap.dedent(
        """
        You are a Bible study assistant. Rules:
        1) Work from the provided notes and Scripture.
        2) Use observation → interpretation → application.
        3) Be concise; use lists when helpful.
        4) Cite Scripture (e.g., James 2:14–26).
        5) If multiple readings exist, list options with pros/cons.
        6) Define specialized terms briefly.
        7) Mark speculation.
        8) Avoid extra-biblical sources unless invited.
        """
    ).strip()

# ---------------- Chunking & Ranking ----------------

TOKEN_WORD_RE = re.compile(r"[A-Za-z0-9']+")


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def tokenize(text: str) -> list[str]:
    return TOKEN_WORD_RE.findall(text.lower())


def split_markdown_into_chunks(md: str, chunk_chars: int = 1800) -> list[str]:
    """Greedy split by headings and paragraphs to ~chunk_chars."""
    if not md:
        return []
    # Prefer splitting at headings first
    parts = re.split(r"\n(?=#+\s)", md)
    chunks: list[str] = []
    buf = []
    size = 0
    def flush():
        nonlocal buf, size
        if buf:
            chunks.append(normalize_ws("\n".join(buf)).strip())
            buf, size = [], 0
    for part in parts:
        if len(part) > chunk_chars * 1.2:
            # further split by paragraphs if huge
            paras = re.split(r"\n\s*\n", part)
            for para in paras:
                if size + len(para) > chunk_chars and size > 0:
                    flush()
                buf.append(para)
                size += len(para)
            flush()
        else:
            if size + len(part) > chunk_chars and size > 0:
                flush()
            buf.append(part)
            size += len(part)
    flush()
    # Drop trivial chunks
    return [c for c in chunks if len(c) > 4]


def build_corpus_chunks(note_files: List[Path], strip_front_matter: bool, chunk_chars: int) -> list[tuple[str, str]]:
    """Return [(chunk_id, text)] using filename indexes."""
    corpus: list[tuple[str, str]] = []
    for idx, p in enumerate(note_files):
        text = read_markdown_file(p, strip_front_matter=strip_front_matter)
        if not text:
            continue
        # Remove common noise (simple heuristics)
        text = re.sub(r"```[\s\S]*?```", " ", text)  # strip code fences
        text = re.sub(r"\n\s*\[\[.*?\]\]\s*\n", "\n", text)  # wiki backlinks
        pieces = split_markdown_into_chunks(text, chunk_chars=chunk_chars)
        for j, c in enumerate(pieces):
            cid = f"{p.name}::chunk{j+1}"
            corpus.append((cid, c))
    return corpus


def build_tfidf_index(chunks: list[tuple[str, str]]):
    docs = {cid: tokenize(txt) for cid, txt in chunks}
    if not docs:
        return {}, {}, {}
    N = len(docs)
    df = Counter(t for tokens in docs.values() for t in set(tokens))
    idf = {t: math.log((N + 1) / (df[t] + 1)) + 1 for t in df}
    norms = {}
    tfidf = {}
    for cid, toks in docs.items():
        tf = Counter(toks)
        vec = {t: (tf[t] * idf.get(t, 0.0)) for t in tf}
        tfidf[cid] = vec
        norms[cid] = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return tfidf, idf, norms


def rank_chunks(query: str | None, tfidf, idf, norms) -> list[str]:
    if not tfidf:
        return []
    if not query:
        # No query: return in stable order
        return list(tfidf.keys())
    qtokens = tokenize(query)
    qtf = Counter(qtokens)
    qvec = {t: (qtf[t] * idf.get(t, 0.0)) for t in qtf}
    qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1.0
    scores = []
    for cid, vec in tfidf.items():
        dot = sum(qvec.get(t, 0.0) * vec.get(t, 0.0) for t in qvec)
        denom = qnorm * (norms.get(cid, 1.0) or 1.0)
        scores.append((dot / denom if denom else 0.0, cid))
    scores.sort(reverse=True)
    return [cid for _, cid in scores]

# ---------------- Tokens & Pricing ----------------

def count_tokens(model: str, *texts: str) -> int:
    if not tiktoken:
        # Fallback rough estimate: 4 chars/token
        return sum(max(1, len(t or "") // 4) for t in texts)
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return sum(len(enc.encode(t or "")) for t in texts)


def estimate_cost(model: str, in_tok: int, out_tok: int) -> float:
    p = MODEL_PRICES.get(model)
    if not p:
        return 0.0
    return (in_tok / 1000000.0) * p.get("in", 0.0) + (out_tok / 1000000.0) * p.get("out", 0.0)

# ---------------- OpenAI ----------------

def create_client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY")
    return OpenAI(api_key=key)


def call_openai_chat(
    args,
    client: OpenAI,
    model: str,
    system_text: str,
    user_content: str,
    temperature: float,
    max_tokens: int | None,
    stream: bool,
):
    # TODO: Fix streaming
    stream = False

    messages=[
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_content},
    ]
    if args.verbose:
        print(f"[Messages] {pp.pformat(messages)}")
    if stream:
        with client.chat.completions.with_streaming_response.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ) as response:
            out = []
            for event in response.iter_lines():
                if event is None:
                    continue
                if hasattr(event, "choices") and event.choices:
                    delta = event.choices[0].delta
                    if delta and delta.get("content"):
                        text = delta["content"]
                        out.append(text)
                        print(text, end="", flush=True)
            print()
            return "".join(out)
    else:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        print(f"[Output]\n{text}")
        return text

# ---------------- Cache ----------------

CACHE_DIR = Path(os.environ.get("SMART_NOTES_CACHE", Path.home() / ".smart_notes_cache"))


def cache_key(model: str, system_text: str, question: str | None, chunk_ids: list[str]) -> str:
    payload = json.dumps([model, system_text, question, chunk_ids], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def cache_read(key: str) -> str | None:
    try:
        p = CACHE_DIR / key
        if p.exists():
            return p.read_text(encoding="utf-8")
    except Exception:
        pass
    return None


def cache_write(key: str, text: str) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / key).write_text(text, encoding="utf-8")
    except Exception:
        pass

# ---------------- CLI glue ----------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bible_cli",
        description="Send Markdown notes + Markdown instructions to OpenAI for Bible study (cost-efficient).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    gsel = p.add_argument_group("Selection")
    gsel.add_argument("--note", action="append", type=Path, default=[], help="Path to a Markdown note. Repeatable.")
    gsel.add_argument("--dir", action="append", type=Path, default=[], help="Directory of Markdown notes. Repeatable.")
    gsel.add_argument("--recursive", action="store_true", help="When using --dir, include subdirectories.")
    gsel.add_argument("--instructions", "-i", action="append", type=Path, default=[], help="Markdown instruction file(s).")

    gctx = p.add_argument_group("Context formatting")
    gctx.add_argument("--include-file-names", action="store_true", help="Label chunks with filenames in the context.")
    gctx.add_argument("--keep-front-matter", action="store_true", help="Do NOT strip YAML front matter from notes.")
    gctx.add_argument("--chunk-size", type=int, default=1800, help="Target characters per chunk before ranking.")
    gctx.add_argument("--top-k", type=int, default=1000, help="Send only the top K ranked chunks.")

    gqa = p.add_argument_group("Prompt")
    gqa.add_argument("--question", "-q", type=str, default=None, help="The question or task for the assistant.")
    gqa.add_argument("--prepend", type=str, default=None, help="Optional text to prepend to the user message.")

    gapi = p.add_argument_group("OpenAI")
    gapi.add_argument("--model", type=str, default="gpt-4o", help="OpenAI chat model name.")
    gapi.add_argument("--temperature", type=float, default=0.3, help="Sampling temperature.")
    gapi.add_argument("--max-tokens", type=int, default=700, help="Max tokens in the response.")
    gapi.add_argument("--no-stream", action="store_true", help="Disable streaming output.")
    gapi.add_argument("--max-context-tokens", type=int, default=10000, help="Hard cap on input tokens; truncate if exceeded.")
    gapi.add_argument("--max-price", type=float, default=0.10, help="Abort if estimated USD cost would exceed this amount.")

    gout = p.add_argument_group("Output")
    gout.add_argument("--out", type=Path, default=None, help="Write the assistant's response to this file.")
    gout.add_argument("--print-context-summary", action="store_true", help="Print how many chunks and characters were sent.")
    gout.add_argument("--dry-run", action="store_true", help="Do not call the API; show selection and estimates.")
    gout.add_argument("--no-cache", action="store_true", help="Disable response cache lookup/write.")
    gout.add_argument("--verbose", action="store_true", help="Increase output to verbose")

    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Gather notes
    note_files = gather_notes(args.note, args.dir, args.recursive)
    if args.verbose:
        print(f"[Notes] {pp.pformat(note_files)}", file=sys.stderr)

    # Build chunks and index
    corpus = build_corpus_chunks(
        note_files,
        strip_front_matter=not args.keep_front_matter,
        chunk_chars=args.chunk_size,
    )
    # print(f"[Corpus] {pp.pformat(corpus)}", file=sys.stderr)

    tfidf, idf, norms = build_tfidf_index(corpus)
    # print(f"[tfidf] {pp.pformat(tfidf)}", file=sys.stderr)
    # print(f"[idf] {pp.pformat(idf)}", file=sys.stderr)
    # print(f"[norms] {pp.pformat(norms)}", file=sys.stderr)

    ranked_ids = rank_chunks(args.question or args.prepend, tfidf, idf, norms)
    # print(f"[Ranked ids] {pp.pformat(ranked_ids)}", file=sys.stderr)

    # Select top-K chunks
    top_ids = ranked_ids[: max(1, args.top_k)]
    id_to_text = {cid: txt for cid, txt in corpus}
    selected_texts = [id_to_text[cid] for cid in top_ids if cid in id_to_text]
    # print(f"[top_ids] {pp.pformat(top_ids)}", file=sys.stderr)
    # print(f"[Selected texts] {pp.pformat(selected_texts)}", file=sys.stderr)

    # Build context block
    def label_block(cid: str, body: str) -> str:
        return f"\n\n## ⟪{cid}⟫\n\n{body}" if args.include_file_names else f"\n\n{body}"

    context_md = "".join(label_block(cid, body) for cid, body in zip(top_ids, selected_texts)).strip()
    if args.prepend:
        context_md = f"{args.prepend.strip()}\n\n{context_md}" if context_md else args.prepend.strip()
    # print(f"[Context Markdown] {pp.pformat(context_md)}", file=sys.stderr)

    # Instructions → system prompt
    system_text = gather_instructions(args.instructions)
    # print(f"[System Text] {pp.pformat(system_text)}", file=sys.stderr)

    # Token & price estimates
    tokens_in = count_tokens(args.model, system_text, context_md, (args.question or ""))
    est_out = args.max_tokens or 0
    est_cost = estimate_cost(args.model, tokens_in, est_out)

    if args.print_context_summary:
        total_chars = sum(len(t) for t in selected_texts)
        if args.verbose:
            print(f"[Model Prices] {pp.pformat(MODEL_PRICES)}, file=sys.stderr")
        print(f"[Model] {args.model}, file=sys.stderr")
        print(
            f"[Context] {len(selected_texts)} chunk(s), {total_chars} characters, ~{tokens_in} input tokens.",
            file=sys.stderr,
        )
        if est_cost:
            print(f"[Estimate] output {est_out} tokens ⇒ ~${est_cost:.4f}", file=sys.stderr)

    # Enforce caps/budget
    if tokens_in > args.max_context_tokens:
        # Truncate by reducing K
        # Keep trimming until under cap or only 1 chunk remains
        k = len(top_ids)
        while tokens_in > args.max_context_tokens and k > 1:
            k -= 1
            top_ids = top_ids[:k]
            selected_texts = [id_to_text[cid] for cid in top_ids]
            context_md = "".join(label_block(cid, body) for cid, body in zip(top_ids, selected_texts)).strip()
            if args.prepend:
                context_md = f"{args.prepend.strip()}\n\n{context_md}" if context_md else args.prepend.strip()
            tokens_in = count_tokens(args.model, system_text, context_md, (args.question or ""))
        print(f"[Trimmed] Using top {k} chunk(s) to satisfy --max-context-tokens.", file=sys.stderr)

    if args.max_price is not None and est_cost and est_cost > args.max_price:
        print(f"[Abort] Est. cost ${est_cost:.4f} exceeds --max-price ${args.max_price:.2f}.", file=sys.stderr)
        if args.dry_run:
            return 0
        return 4

    if args.dry_run:
        # Show IDs and exit
        print("[Dry run] Selected chunks:", file=sys.stderr)
        for cid in top_ids:
            print(f"  - {cid}", file=sys.stderr)
        print(f"~{tokens_in} input tokens; planning for {est_out} output tokens.", file=sys.stderr)
        if est_cost:
            print(f"Estimated cost: ${est_cost:.4f}", file=sys.stderr)
        return 0

    # Compose user message
    user_content = context_md if not args.question else f"{context_md}\n\n# User question\n{args.question}"
    if args.verbose:
        print(f"[User content] {user_content}", file=sys.stderr)

    # Cache check
    cache_hit = None
    key = cache_key(args.model, system_text, args.question, top_ids)
    if args.verbose:
        print(f"[Cache key] {key}", file=sys.stderr)
    if not args.no_cache:
        cache_hit = cache_read(key)
        if cache_hit is not None:
            if args.verbose:
                print("[Cache hit]", file=sys.stderr)
            print(cache_hit)
            if args.out:
                try:
                    args.out.parent.mkdir(parents=True, exist_ok=True)
                    args.out.write_text(cache_hit, encoding="utf-8")
                    print(f"\n[Saved]\n{args.out}", file=sys.stderr)
                except Exception as e:
                    sys.stderr.write(f"Could not write output file: {e}\n")
                    return 3
            return 0

    # OpenAI call
    client = create_client()
    try:
        output = call_openai_chat(
            args=args,
            client=client,
            model=args.model,
            system_text=system_text,
            user_content=user_content,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            stream=not args.no_stream,
        )
    except Exception as e:
        sys.stderr.write(f"OpenAI error: {e}\n")
        return 2

    # cache
    if output and not args.no_cache:
        if args.verbose:
            print(f"[Updating cache] key={key}", file=sys.stderr)
        cache_write(key, output)

    # save
    if args.out:
        try:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(output, encoding="utf-8")
            print(f"\n[Saved] {args.out}", file=sys.stderr)
        except Exception as e:
            sys.stderr.write(f"Could not write output file: {e}\n")
            return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
