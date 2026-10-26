"""Extract loanword candidates from a kaikki.org Wiktionary extract.

    python -I tools/wiktionary_loans.py sources/kaikki/uk.jsonl \\
        [--vesum sources/dict_corp_vis.txt] [--stats] [-o sources/loan_candidates.tsv]

Reads Ukrainian entries whose etymology says they were borrowed or derived
from a word in a modern Latin-script language, and writes candidates for
review:

    latin<TAB>cyrillic<TAB>indeclinable<TAB>source language<TAB>source spelling

`latin` is the source word without accents (vélocipède → velocipede). Pairs the
IME already converts correctly are left out, and with --vesum, nouns VESUM tags
as indeclinable (`:nv`, like ательє, досьє) are marked and listed first.
Nothing is added to the IME automatically: copy the entries you want into a
.loans file.
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Etymology templates: borrowed, learned borrowing, orthographic borrowing, derived.
RELATIONS = {"bor", "bor+", "lbor", "obor", "der", "der+"}
# Modern languages written in Latin script; Slavic and historical stages are left out.
DONORS = {"fr", "de", "en", "it", "es", "pt", "nl", "ca", "ro", "hu", "sv", "da", "no", "nb", "fi", "et",
          "lt", "lv", "tr", "sq", "eu", "ga", "cy", "is"}
LATIN_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-žƀ-ɏ'’]+")
CYRILLIC_WORD = re.compile(r"[а-щьюяєіїґА-ЩЬЮЯЄІЇҐ'’ʼ]+")
INDECLINABLE = re.compile(r"^\s*(\S+) noun:(?:anim|inanim|unanim):[mfnp]:v_naz:nv(?::(?!prop|abbr)\S*)?(?:\s|$)")
SPECIAL = str.maketrans({"ß": "ss", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe", "ø": "o", "Ø": "O", "ł": "l", "’": "'"})


def without_accents(word: str) -> str:
    word = unicodedata.normalize("NFKD", word.translate(SPECIAL))
    return "".join(c for c in word if not unicodedata.combining(c))


def candidates(path: str):
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # e.g. a cut-off last line while downloading
            if entry.get("lang_code") != "uk":
                continue
            word = entry.get("word", "")
            if not CYRILLIC_WORD.fullmatch(word):
                continue
            for template in entry.get("etymology_templates", []):
                if template.get("name") not in RELATIONS:
                    continue
                args = template.get("args", {})
                if args.get("1") != "uk":
                    continue
                source_lang, source = args.get("2", ""), args.get("3", "").strip()
                if source_lang in DONORS and LATIN_WORD.fullmatch(source):
                    yield source, word, source_lang
                break  # only the first (nearest) etymology step


def indeclinables(vesum: str) -> set[str]:
    words = set()
    with open(vesum, encoding="utf-8") as f:
        for line in f:
            if ":nv" in line and (m := INDECLINABLE.match(line)):
                words.add(m.group(1).lower())
    return words


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("extract")
    parser.add_argument("--vesum", help="VESUM dict_corp_vis.txt, to mark indeclinable nouns")
    parser.add_argument("-o", "--output")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    from composer import Composer  # noqa: E402  (imported late: loads the rules and lexicon)

    nv = indeclinables(args.vesum) if args.vesum else set()
    seen, rows, handled = set(), [], 0
    for source, word, lang in candidates(args.extract):
        latin = without_accents(source)
        if (latin.lower(), word) in seen:
            continue
        seen.add((latin.lower(), word))
        c = Composer("uk")
        for ch in latin:
            c.push(ch)
        if c.candidates()[0].lower() == word.lower():
            handled += 1  # the rules or the list already get it right
            continue
        rows.append((latin, word, "yes" if word.lower() in nv else "", lang, source))

    rows.sort(key=lambda r: (r[2] != "yes", r[3], r[0].lower()))
    if args.stats:
        by_lang = Counter(r[3] for r in rows)
        print(f"{len(rows) + handled} pairs from modern Latin-script languages; "
              f"{handled} already converted correctly, {len(rows)} left for review, "
              f"{sum(r[2] == 'yes' for r in rows)} of them indeclinable")
        for lang, n in by_lang.most_common():
            print(f"  {lang:4} {n:5}  " + ", ".join(f"{r[0]}→{r[1]}" for r in rows if r[3] == lang)[:120])
        print("  indeclinable: " + ", ".join(f"{r[0]}→{r[1]}" for r in rows if r[2] == "yes")[:400])
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("# latin\tcyrillic\tindeclinable\tsource language\tsource spelling\n")
            for row in rows:
                f.write("\t".join(row) + "\n")
        print(f"wrote {len(rows)} candidates to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
