import itertools
import re
import unittest
from pathlib import Path

from rules import RuleTable
from tests.fsm_oracle import Transliterator

DATA = Path(__file__).parent.parent / "data"

# Inputs where the rule table intentionally differs from the old FSM (FSM bugs).
INTENDED = re.compile("|".join([
    r"Cc",                # Cc gave Цц instead of Ц
    r"J''",               # uppercase J after a consonant ignored the apostrophe
    r"(?i:wc|cw)",        # w then c (or c then w) lost the pending digraph
    r"(?i:'j[^aeiouj'])",  # C'j + consonant dropped the apostrophe
    r"(?i:jjj|jj'')",     # й from the jj escape now counts as a consonant everywhere
    r"(?i:[aeiouy]i)",    # і after a vowel is ї (країна), as in Ukrainian spelling
    r"(?i:[wq])",         # w and q are в and к; ш, ч, щ are typed š, č, šč (s`, c`)
    r"(?i:jj|cc|'')",     # no escapes: the lexicon resolves splits (мільйон: miljjon)
]))


def fsm(s: str) -> str:
    t = Transliterator()
    return "".join(t.feed(c) for c in s) + t.flush()


class GoldenTest(unittest.TestCase):

    def test_native_matches_fsm(self):
        table = RuleTable.load(DATA / "uk.rules")
        diffs = []
        for n in range(1, 5):
            for chars in itertools.product("aeiouyjJwWcCqhnst'A", repeat=n):
                s = "".join(chars)
                if INTENDED.search(s):
                    continue
                if table.native(s) != fsm(s):
                    diffs.append(f"{s!r}: rules {table.native(s)!r}, fsm {fsm(s)!r}")
        self.assertEqual(diffs[:40], [], f"{len(diffs)} differences")


if __name__ == "__main__":
    unittest.main()
