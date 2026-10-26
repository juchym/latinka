"""Build data/<lang>.db from word lists.

Input: one `word [count]` per line (whitespace-separated, as in frequency
lists), any case. Lines that aren't Cyrillic words are skipped, as are forms
VESUM tags as non-standard (`:bad`). Counts of the same word from several
sources are added up. Words that only occur with VESUM's proper-noun or
abbreviation tags (`:prop`, or `:abbr` when spelled with capitals like БЮТ) are
marked proper, and those only
tagged as non-standard variant spellings (`:alt`) are marked variant. Forms
tagged as infinitives (`:inf`) are marked infinitive.

Files given with --counts only contribute counts, never new words, so a
noisy frequency list can rank a clean form dictionary:

    python tools/build_lexicon.py uk sources/dict_corp_vis.txt --counts sources/uk_full.txt
"""

import argparse
import os
import re
import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lexicon import SCHEMA, normalize  # noqa: E402

WORD = re.compile(r"[а-яёіїєґ']+")
BAD_TAG = re.compile(r"(^|:)bad(:|$)")
PROPER_TAG = re.compile(r"(^|:)prop(:|$)")
ABBR_TAG = re.compile(r"(^|:)abbr(:|$)")
VARIANT_TAG = re.compile(r"(^|:)alt(:|$)")
INFINITIVE_TAG = re.compile(r"(^|:)inf(:|$)")


def read(path: str) -> Iterator[tuple[str, int, bool, bool, bool]]:
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            fields = line.split()
            if not fields:
                continue
            word = normalize(fields[0]).strip("'")
            if not WORD.fullmatch(word):
                continue
            if len(fields) > 1 and BAD_TAG.search(fields[1]):
                continue
            tags = fields[1] if len(fields) > 1 else ""
            # Names, and abbreviations spelled with capitals (БЮТ, НАТО), need a capital to match;
            # lowercase abbreviations (г, кг, км) are ordinary words.
            proper = bool(PROPER_TAG.search(tags)) or (bool(ABBR_TAG.search(tags)) and fields[0] != fields[0].lower())
            yield (word, int(tags) if tags.isdigit() else 0, proper,
                   bool(VARIANT_TAG.search(tags)), bool(INFINITIVE_TAG.search(tags)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lang")
    parser.add_argument("sources", nargs="+", help="word lists that define the vocabulary")
    parser.add_argument("--counts", nargs="+", default=[], help="lists that only add counts to known words")
    args = parser.parse_args()

    counts: dict[str, int] = {}
    proper: dict[str, bool] = {}
    variant: dict[str, bool] = {}
    infinitive: dict[str, bool] = {}
    for src in args.sources:
        for word, count, is_proper, is_variant, is_infinitive in read(src):
            counts[word] = counts.get(word, 0) + count
            proper[word] = proper.get(word, True) and is_proper
            variant[word] = variant.get(word, True) and is_variant
            infinitive[word] = infinitive.get(word, False) or is_infinitive
    for src in args.counts:
        for word, count, _, _, _ in read(src):
            if word in counts:
                counts[word] += count

    out = Path(__file__).parent.parent / "data" / f"{args.lang}.db"
    tmp = out.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.execute("PRAGMA journal_mode = OFF")
    db.execute("PRAGMA synchronous = OFF")
    db.execute(SCHEMA)
    db.executemany("INSERT INTO words VALUES (?, ?, ?, ?, ?)",
                   ((w, counts[w], int(proper[w]), int(variant[w]), int(infinitive[w])) for w in sorted(counts)))
    db.commit()
    db.close()
    os.replace(tmp, out)  # never leave a half-written lexicon in place
    print(f"{out}: {len(counts)} words, {sum(1 for c in counts.values() if c)} with counts, "
          f"{sum(proper.values())} proper nouns, {sum(variant.values())} variants, "
          f"{sum(infinitive.values())} infinitives")


if __name__ == "__main__":
    main()
