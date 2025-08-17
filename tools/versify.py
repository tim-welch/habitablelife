import argparse
import os
import pathlib
import re

parser = argparse.ArgumentParser(
    prog="Versify",
    description="""Break full text Bible into individual verse files.
        The file should be 1 line per verse.
        Each line should be prefixed with <Book> <chapter>:<verse> followed by the verse.
        The first lines may not have the verse prefix. These are assumed to be information about the translation and will be placed in their own file at the root of the tree.
        Each verse is placed in a file in this format: <Book>/<Chapter>/<verse>.md""",
)

parser.add_argument("-b", "--bible", type=pathlib.Path, help="file containing the bible text")
parser.add_argument("-o", "--output", required=True, type=pathlib.Path, help="the folder to versify the bible into")

args = parser.parse_args()
bible = args.bible
output_dir : pathlib.Path = args.output
print(f"Source Bible: {bible}")
print(f"Output Directory: {output_dir}")

with open(bible, encoding="utf-8") as f:
    lines = f.readlines()

print(f"This Bible document contains {len(lines)} lines.")

bible_verses = {
    "copyright": [],
    "books": {},
}

verse_pattern = re.compile(
    r"""^
    ([1-3]?\s?[A-Z][a-z]+(?:\s(?:of|the|[A-Z][a-z]+))*)  # Book name (group 1)
    \s
    (\d+)                                               # Chapter (group 2)
    :
    (\d+)                                               # Verse (group 3)
    \s+
    (.*)                                                # Verse text (group 4)
    $""",
    re.VERBOSE
)

book_num = 0
for line in lines:
    match = verse_pattern.match(line)
    if match:
        book = match.group(1)
        chapter = match.group(2)
        verse = match.group(3)
        text = match.group(4)
        if not book in bible_verses["books"]:
            book_num = book_num + 1
            bible_verses["books"][book] = { "book_num": book_num, "chapters": {} }
        if not chapter in bible_verses["books"][book]["chapters"]:
            bible_verses["books"][book]["chapters"][chapter] = {}
        bible_verses["books"][book]["chapters"][chapter][verse] = text
    else:
        bible_verses["copyright"].append(line)

# Build the verse tree
os.makedirs(output_dir, exist_ok=True)
with open(output_dir.joinpath("copyright.md"), "wt", encoding="utf-8") as f:
    f.writelines(bible_verses["copyright"])

chapters = 0
verses = 0
for book in bible_verses["books"]:
    book_num = bible_verses["books"][book]["book_num"]
    book_dir = output_dir.joinpath(f"{book_num:02d}-{book}")
    os.makedirs(book_dir, exist_ok=True)
    for chapter in bible_verses["books"][book]["chapters"]:
        chapters = chapters + 1
        # chapter_dir = book_dir.joinpath(f"{book} {chapter}")
        chapter_dir = book_dir
        chapter_file = chapter_dir.joinpath(f"{book} {chapter}.md")
        os.makedirs(chapter_dir, exist_ok=True)
        with open(chapter_file, "wt", encoding="utf-8") as fchapter:
            fchapter.write(f"# {book} {chapter}\n")
            for verse in bible_verses["books"][book]["chapters"][chapter]:
                verses = verses + 1
                verse_text = bible_verses["books"][book]["chapters"][chapter][verse]
                fchapter.write(f"## {verse}\n{verse_text}\n")
                # fchapter.write(f"## {book} {chapter}:{verse}\n{verse_text}\n")
                # verse_file = chapter_dir.joinpath(f"{book} {chapter}_{verse}.md")
                # with open(verse_file, "wt", encoding="utf-8") as f:
                #     f.writelines([
                #         f"# {book} {chapter}:{verse}\n\n",
                #         verse_text,
                #         "\n"])

# Summary
print(f"Found {len(bible_verses["books"])} books, {chapters} chapters, and {verses} verses in this translation")
print(bible_verses["copyright"])
