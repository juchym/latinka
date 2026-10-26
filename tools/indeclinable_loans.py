"""Find source spellings for indeclinable Ukrainian nouns (ательє, бюро, кіно…).

    python -I tools/indeclinable_loans.py sources/dict_corp_vis.txt \\
        fr:sources/fr_full.txt it:sources/it_full.txt en:sources/en_full.txt ... \\
        [--top 200000] [-o sources/indeclinable_candidates.tsv]

Targets are the nouns VESUM tags as indeclinable (`:nv`, not names or
abbreviations). Each word of a foreign frequency list is read with rules for
its own language, every combination of readings is tried, and a word is kept
when one of its readings is exactly a target. Pairs the IME already converts
correctly are left out, and so are targets of three letters or fewer (almost
all coincidences). For each target the best three source spellings are kept:
fewest silent letters and secondary readings, then most languages agreeing,
then most frequent. The output is for review, nothing is added to the IME:

    latin<TAB>cyrillic<TAB>cost<TAB>languages<TAB>frequency rank<TAB>source spellings

With --add-variants FILE.loans, instead append to each line of a reviewed
loanword list the forms VESUM marks non-standard (`:bad`) or as variants
(`:alt`) that the same source spelling reaches (spaghetti спагеті → spaghetti
спагеті спагетті), so the IME offers them after the standard form.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from wiktionary_loans import without_accents  # noqa: E402

TARGET = re.compile(r"^(\S+) noun:(?:anim|inanim|unanim):[mfnp]:v_naz:nv(?::(?!prop|abbr)\S*)?(?:\s|$)")
CYRILLIC = re.compile(r"[а-щьюяєіїґ']+")
VOWELS = set("aeiouyàâäéèêëîïôöùûüœæãõáíóú")

# A rule is (pattern, readings, condition). Conditions: "" anywhere, "^" at the
# start, "$" at the end, "ei" before e/i/y, "V" between vowels.
BASE = """
a а,я | b б | c к | d д | e е,є | f ф | g г | h -,г,х | i і,и,й | j ж,й | k к | l л,ль | m м | n н
o о | p п | q к | r р | s с | t т | u у,ю | v в | w в | x кс | y і,и,й | z з
ph ф | th т | ck к | sh ш | ss с | ll л,ль | tt т | nn н,нн | mm м | pp п | rr р | ff ф | cc к | bb б | dd д | gg г
""".strip()

LANGS = {
    "fr": """
eau о | au о | ou у | oi уа | oy уай,ой | ai е | ei е | eu е,ьо | œu е | u ю,у | é е,є | è е | ê е | ë е | à а | â а
î і | ï ї | ô о | û ю,у | ç с | ch ш | qu к | gn нь | ill й,ль | ille ій,ль | j ж | c^ei с | g^ei ж
an ан | en ан,ен | on он | in ен,ін | un ен | am ам | em ам | s^V з
ier$ ьє,є | er$ є,е | et$ е,ет | ez$ е | e$ - | es$ - | s$ - | t$ - | x$ - | d$ - | é$ е | ée$ е
""",
    "it": """
c^ei ч | ci^V ч | ch к | g^ei дж | gi^V дж | gh г | gli ль,льї | gn нь | sc^ei ш | sci^V ш | z ц,дз | zz ц | qu кв
e е | i і,и | j й | h -
""",
    "es": """
j х | ll ль,й | ñ нь | c^ei с | z с | qu к | gu^ei г | g^ei х | h - | ch ч | y й,і | v в,б | á а | é е | í і | ó о | ú у
""",
    "pt": """
nh нь | lh ль | ão ан,ау | õe он | ç с | x ш | ch ш | j ж | g^ei ж | qu к | o$ у,о | e$ е,і | á а | é е | ê е | í і | ó о | ô о | ú у | ã а
""",
    "de": """
sch ш | ch х | ei ай,ей | ie і | eu ой | äu ой | tz ц | z ц | v ф | w в | s^V з | ^st шт | ^sp шп | ä е | ö е | ü ю | ß с | h -
""",
    "en": """
ee і | ea і | oo у | ou ау,у | ow ау,оу | a а,е,ей | i і,ай | u а,у,ю | e$ - | ch ч | th т,з | j дж | g^ei дж | c^ei с | qu кв | w в,у | y і,и,й,ай
""",
}


def parse(table: str) -> list[tuple[str, list[str], str]]:
    rules = []
    for item in table.replace("\n", "|").split("|"):
        item = item.strip()
        if not item:
            continue
        pattern, readings = item.split()
        condition = ""
        if pattern.startswith("^") and len(pattern) > 1:
            pattern, condition = pattern[1:], "^"
        elif pattern.endswith("$"):
            pattern, condition = pattern[:-1], "$"
        elif "^" in pattern:
            pattern, condition = pattern.split("^")
        rules.append((pattern, ["" if r == "-" else r for r in readings.split(",")], condition))
    return rules


def applies(word: str, i: int, pattern: str, condition: str) -> bool:
    if not word.startswith(pattern, i):
        return False
    end = i + len(pattern)
    following = word[end:end + 1]
    match condition:
        case "^": return i == 0
        case "$": return end == len(word)
        case "ei": return following in ("e", "i", "y", "é", "è", "ê")
        case "V": return i > 0 and word[i - 1] in VOWELS and following in VOWELS
    return True


def readings(word: str, rules, prefixes: set[str], targets: set[str]) -> dict[str, int]:
    """Targets reachable from `word`, with the lowest cost: one point per silent
    letter or secondary reading used."""
    found: dict[str, int] = {}

    def walk(i: int, out: str, cost: int) -> None:
        if i == len(word):
            if out in targets:
                found[out] = min(cost, found.get(out, cost))
            return
        for pattern, outputs, condition in rules:
            if applies(word, i, pattern, condition):
                for k, o in enumerate(outputs):
                    nxt = out + o
                    if nxt in prefixes or nxt == "":
                        walk(i + len(pattern), nxt, cost + (k > 0) + (o == ""))

    walk(0, "", 0)
    return found


def add_variants(args) -> None:
    """Append to each entry of a .loans file the non-standard forms its source spelling reaches."""
    standard, nonstandard = set(), set()
    with open(args.vesum, encoding="utf-8") as f:
        for line in f:
            if ":nv" in line and (m := TARGET.match(line)) and CYRILLIC.fullmatch(m.group(1)):
                (nonstandard if ":bad" in line or ":alt" in line else standard).add(m.group(1))
    nonstandard -= standard
    prefixes = {t[:k] for t in nonstandard for k in range(1, len(t) + 1)}
    rule_sets = [parse(LANGS[spec.split(":", 1)[0]]) + parse(BASE) for spec in args.lists]

    out, added = [], 0
    for line in Path(args.add_variants).read_text(encoding="utf-8").split("\n"):
        body, sep, comment = line.partition("#")
        fields = body.split()
        if len(fields) >= 2:
            latin, forms = fields[0], fields[1:]
            extra = set()
            for rules in rule_sets:
                extra |= set(readings(latin.lower(), rules, prefixes, nonstandard))
            extra = sorted(extra - set(forms))
            if extra:
                added += len(extra)
                forms += extra
                line = f"{latin:<15} {' '.join(forms)}" + (f"   #{comment}" if sep else "")
        out.append(line)
    Path(args.add_variants).write_text("\n".join(out), encoding="utf-8")
    print(f"added {added} non-standard forms to {args.add_variants}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vesum")
    parser.add_argument("lists", nargs="+", help="lang:path frequency lists, e.g. fr:sources/fr_full.txt")
    parser.add_argument("--top", type=int, default=200_000)
    parser.add_argument("-o", "--output")
    parser.add_argument("--add-variants", metavar="LOANS", help="append VESUM's non-standard forms to this list")
    args = parser.parse_args()
    if args.add_variants:
        add_variants(args)
        return

    from composer import Composer  # noqa: E402  (loads the rules and lexicon)

    targets = set()
    with open(args.vesum, encoding="utf-8") as f:
        for line in f:
            # Skip spellings VESUM marks non-standard (лоббі, спагетті): the standard one is the target.
            if ":nv" in line and ":bad" not in line and (m := TARGET.match(line)) and CYRILLIC.fullmatch(m.group(1)):
                targets.add(m.group(1))
    prefixes = {t[:k] for t in targets for k in range(1, len(t) + 1)}
    base = parse(BASE)
    print(f"{len(targets)} indeclinable target nouns", file=sys.stderr)

    rows, matched_by_lang = [], defaultdict(set)
    for spec in args.lists:
        lang, path = spec.split(":", 1)
        rules = parse(LANGS[lang]) + base
        with open(path, encoding="utf-8", errors="replace") as f:
            for rank, line in enumerate(f, 1):
                if rank > args.top:
                    break
                word = line.split(" ", 1)[0].lower()
                if not word.isalpha() or len(word) < 2:
                    continue
                for target, cost in readings(word, rules, prefixes, targets).items():
                    if len(target) > 3:
                        rows.append((without_accents(word), target, lang, word, rank, cost))
                        matched_by_lang[lang].add(target)

    # Merge the languages producing the same spelling for the same target.
    pairs: dict[tuple[str, str], dict] = {}
    for latin, target, lang, word, rank, cost in rows:
        p = pairs.setdefault((latin.lower(), target), {"cost": cost, "langs": set(), "rank": rank, "words": set()})
        p["cost"] = min(p["cost"], cost)
        p["rank"] = min(p["rank"], rank)
        p["langs"].add(lang)
        p["words"].add(f"{lang}:{word}")

    def converts(latin: str, target: str) -> bool:
        c = Composer("uk")
        for ch in latin:
            c.push(ch)
        return c.candidates()[0].lower() == target

    by_target: dict[str, list] = defaultdict(list)
    for (latin, target), p in pairs.items():
        by_target[target].append((p["cost"], -len(p["langs"]), p["rank"], latin, p))
    # A target needs no entry when the IME already converts one of its best spellings.
    handled, kept = set(), []
    for target in sorted(by_target):
        best = sorted(by_target[target])[:3]
        if any(converts(latin, target) for _, _, _, latin, _ in best):
            handled.add(target)
            continue
        for cost, _, rank, latin, p in best:
            kept.append((latin, target, cost, ",".join(sorted(p["langs"])), rank, " ".join(sorted(p["words"]))))
    by_target = {t: v for t, v in by_target.items() if t not in handled}

    matched = {r[1] for r in rows}
    print(f"{len(matched)} of {len(targets)} targets matched ({len(handled)} already reachable in the IME); "
          f"{len(by_target)} targets left for review, {len(kept)} rows", file=sys.stderr)
    for lang, ts in matched_by_lang.items():
        print(f"  {lang}: {len(ts)} targets", file=sys.stderr)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("# latin\tcyrillic\tlanguage\tsource spelling\tfrequency rank\n")
            for row in kept:
                f.write("\t".join(map(str, row)) + "\n")
        with open(Path(args.output).with_suffix(".unmatched.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(targets - matched)) + "\n")
        # The same, as a draft loanword list: delete wrong lines, paste the rest into a .loans file.
        draft = Path(args.output).with_suffix(".loans")
        with open(draft, "w", encoding="utf-8") as f:
            f.write("# Draft: indeclinable nouns and their likely source spelling. Delete wrong lines,\n"
                    "# fix spellings, then copy the rest into ~/.local/share/udnc/uk.loans.\n")
            by_cyrillic: dict[str, list] = defaultdict(list)
            for row in kept:
                by_cyrillic[row[1]].append(row)
            for target, options in by_cyrillic.items():
                best, others = options[0], options[1:]
                note = f"{best[3]}" + (f"; or {', '.join(o[0] for o in others)}" if others else "")
                f.write(f"{best[0]:<16} {target:<14} # {note}\n")
        print(f"wrote {args.output}, {draft} and {Path(args.output).with_suffix('.unmatched.txt')}", file=sys.stderr)


if __name__ == "__main__":
    main()
