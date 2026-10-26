"""Report how many example spellings convert correctly, per tag.

    python tools/check_examples.py [examples/etymology.tsv] [--lang uk] [--failures]

Each example line is `latin<TAB>cyrillic<TAB>tags`. A row counts as first when
the expected word is the top candidate, and as offered when it is anywhere in
the candidate list (reachable with Tab).
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from composer import Composer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", nargs="?", default=Path(__file__).parent.parent / "examples" / "etymology.tsv")
    parser.add_argument("--lang", default="uk")
    parser.add_argument("--failures", action="store_true", help="list the rows that don't come out first")
    args = parser.parse_args()

    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # first, offered, total
    failures = []
    for line in Path(args.file).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        latin, cyrillic, tags = (line.split("\t") + [""])[:3]
        c = Composer(args.lang)
        for ch in latin:
            c.push(ch)
        candidates = c.candidates()
        first, offered = candidates[0] == cyrillic, cyrillic in candidates
        for tag in ["all"] + tags.split(","):
            s = stats[tag]
            s[0] += first
            s[1] += offered
            s[2] += 1
        if not first:
            failures.append((latin, cyrillic, tags, candidates))

    print(f"{'tag':16} {'first':>7} {'offered':>8}")
    for tag in sorted(stats, key=lambda t: (t != "all", t)):
        first, offered, total = stats[tag]
        print(f"{tag:16} {first:3}/{total:<3} {offered:4}/{total:<3}")
    if args.failures:
        print()
        for latin, cyrillic, tags, candidates in failures:
            mark = "offered" if cyrillic in candidates else "missing"
            print(f"{mark:8} {latin:12} want {cyrillic:14} got {candidates[:4]}  [{tags}]")


if __name__ == "__main__":
    main()
