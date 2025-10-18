#!/usr/bin/env python3
"""
Bible Study CLI — send Markdown notes + Markdown instructions to OpenAI.

Usage examples:

  # Single note + instructions, streaming
  python bible_cli.py \
    --note path/to/note.md \
    --instructions path/to/instructions.md \
    --question "Summarize key themes and cross-references."

  # All notes in a directory recursively + multiple instruction files
  python bible_cli.py \
    --dir path/to/notes \
    --instructions instr/base.md instr/study-style.md \
    --question "Trace the argument and list open questions." \
    --include-file-names

  # Save output to a file
  python bible_cli.py \
    --dir ./notes \
    --instructions ./instr.md \
    --question "How does James relate to Paul on faith and works?" \
    --out response.md
"""

from __future__ import annotations

import argparse
import os
import pprint as pp
import sys
import textwrap
from pathlib import Path
from typing import Iterable, List, Tuple

try:
    from openai import OpenAI
except ImportError as e:
    sys.stderr.write("ERROR: openai package not installed. Run: pip install openai\n")
    raise

# Optional: strip YAML front matter if present
import re

FRONT_MATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

# -------- Files --------

def read_markdown_file(path: Path, strip_front_matter: bool = True) -> str:
    text = path.read_text(encoding="utf-8")
    if strip_front_matter:
        text = FRONT_MATTER_RE.sub("", text, count=1)
    return text.strip()

def gather_notes(
    notes: Iterable[Path],
    dirs: Iterable[Path],
    recursive: bool,
) -> List[Path]:
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
        if f.resolve() not in seen:
            seen.add(f.resolve())
            unique.append(f)

    # if not unique:
    #     raise FileNotFoundError("No Markdown notes found.")
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
    # Sensible, Bible-first default. Replace or extend as you like.
    return textwrap.dedent(
        """
        You are a Bible study assistant. Follow these rules:

        1) Base your analysis on the provided notes and on the Bible text itself.
        2) When interpreting, move from observation → interpretation → application.
        3) Prefer clear, concise prose with numbered or bulleted lists when useful.
        4) Cite Scripture by book, chapter, and verse (e.g., James 2:14–26).
        5) If there are multiple plausible readings, lay them out fairly with pros/cons.
        6) Avoid theological jargon unless the user asks for it; define terms briefly.
        7) If a claim is speculative, say so explicitly.
        8) Limit extra-biblical references unless the user explicitly invites them.
        """
    ).strip()

def build_context_block(
    note_files: List[Path],
    include_file_names: bool,
    strip_front_matter: bool,
) -> Tuple[str, int]:
    """
    Returns (context_text, count_of_notes).
    The context is a single Markdown block that concatenates all notes,
    separated by headings that include filenames (optional).
    """
    parts = []
    for p in note_files:
        content = read_markdown_file(p, strip_front_matter=strip_front_matter)
        if include_file_names:
            parts.append(f"\n\n# ⟪{p.name}⟫\n\n{content}")
        else:
            parts.append(f"\n\n{content}")
    context = "\n".join(parts).strip()
    return context, len(note_files)

# -------- OpenAI --------

def create_client() -> OpenAI:
    # Requires OPENAI_API_KEY in env. You can also set OPENAI_BASE_URL if needed.
    # return OpenAI()
    return None

def call_openai_chat(
    client: OpenAI,
    model: str,
    system_text: str,
    context_md: str,
    question: str | None,
    temperature: float,
    max_tokens: int | None,
    stream: bool,
):
    """
    Compose messages as:
      - system: instructions
      - user: context block + question (if provided)
    """
    user_content = context_md if not question else f"{context_md}\n\n### User question\n{question}"
    messages=[
        {"role": "system", "content": system_text},
        {"role": "user", "content": user_content},
    ]
    
    pp.pprint(messages)
    print(f"model={model}")
    print(f"temperature={temperature}")
    print(f"max_tokens={max_tokens}")
    return "openai response"

    if stream:
        # Stream tokens to stdout as they arrive.
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
                # SDK prints chunks by itself in some versions; to be safe, print choices deltas when present.
                if hasattr(event, "choices") and event.choices:
                    delta = event.choices[0].delta
                    if delta and delta.get("content"):
                        text = delta["content"]
                        out.append(text)
                        print(text, end="", flush=True)
            print()  # newline at end
            return "".join(out)
    else:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_content},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content or ""
        print(text)
        return text

# -------- CLI --------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bible_cli",
        description="Send Markdown notes + Markdown instructions to OpenAI for Bible study.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    gsel = p.add_argument_group("Selection")
    gsel.add_argument("--note", action="append", type=Path, default=[], help="Path to a single Markdown note. Repeatable.")
    gsel.add_argument("--dir", action="append", type=Path, default=[], help="Directory containing Markdown notes (.md). Repeatable.")
    gsel.add_argument("--recursive", action="store_true", help="When using --dir, include subdirectories.")
    gsel.add_argument("--instructions", "-i", action="append", type=Path, default=[],
                      help="Markdown instruction file(s) for the system prompt. If omitted, a sensible default is used.")

    gctx = p.add_argument_group("Context formatting")
    gctx.add_argument("--include-file-names", action="store_true", default=True, help="Prefix each note with a heading containing the filename.")
    gctx.add_argument("--keep-front-matter", action="store_true", help="Do NOT strip YAML front matter from notes.")

    gqa = p.add_argument_group("Prompt")
    gqa.add_argument("--question", "-q", type=str, default=None, help="The question or task for the assistant.")
    gqa.add_argument("--prepend", type=str, default=None,
                     help="Optional text to prepend to the user message (e.g., global constraints).")

    gapi = p.add_argument_group("OpenAI")
    gapi.add_argument("--model", type=str, default="gpt-5.1",
                      help="OpenAI chat model name.")
    gapi.add_argument("--temperature", type=float, default=0.3, help="Sampling temperature.")
    gapi.add_argument("--max-tokens", type=int, default=None, help="Max tokens in the response.")
    gapi.add_argument("--no-stream", action="store_true", help="Disable streaming output.")

    gout = p.add_argument_group("Output")
    gout.add_argument("--out", type=Path, default=None, help="Write the assistant's response to this file.")
    gout.add_argument("--print-context-summary", action="store_true",
                      help="Print how many notes and total characters were sent.")

    return p.parse_args()

def main() -> int:
    args = parse_args()

    # Collect notes
    note_files = gather_notes(args.note, args.dir, args.recursive)
    context_md, count = build_context_block(
        note_files,
        include_file_names=args.include_file_names,
        strip_front_matter=not args.keep_front_matter,
    )

    if args.prepend:
        context_md = f"{args.prepend.strip()}\n\n{context_md}"

    # Instructions → system prompt
    system_text = gather_instructions(args.instructions)

    if args.print_context_summary:
        total_chars = sum(len(read_markdown_file(p, strip_front_matter=not args.keep_front_matter)) for p in note_files)
        print(f"[Context] {count} note(s), {total_chars} characters.", file=sys.stderr)

    # OpenAI call
    client = create_client()
    try:
        output = call_openai_chat(
            client=client,
            model=args.model,
            system_text=system_text,
            context_md=context_md,
            question=args.question,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            stream=not args.no_stream,
        )
    except Exception as e:
        sys.stderr.write(f"OpenAI error: {e}\n")
        return 2

    # Save if requested
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
