"""Data-driven Latin -> Cyrillic transducer.

A rule table (data/<lang>.rules) lists rows of `ctx latin cyrillic cost`:

  ctx   condition on the last Cyrillic character produced so far (or the
        character before the word): `*` any, `C` a Cyrillic consonant,
        `!C` anything else, including the start of text, or a literal set of
        characters such as `ьЬ`.
  latin lowercase Latin sequence to match. A leading `^` makes it match only
        at the start of the word and a trailing `$` only at the end; a
        trailing `/C` only before a consonant (syllabic r and l: `r/C` in krv,
        but not in dobre), `/V` only before a vowel, and `/+` only before more
        letters (an ending).
  cyrillic  the output; `-` for none (French silent letters).
  cost  0 for native rules, >= 1 for alternatives (loanwords etc.), or `inf`
        for an infinitive ending (choditi): an alternative that beats the
        native reading when it produces an infinitive.

Native rules are applied deterministically with longest match. Alternatives
are only explored by `readings()`, which keeps paths whose output is a real
word in the lexicon. Among real words, a native reading comes first, then
alternatives by frequency.

A loanword list (data/<lang>.loans, lines of `latin cyrillic [cyrillic…]`)
adds words from living languages, which follow no rules: bureau бюро,
Tiananmen Тяньаньмень. Further forms on a line are offered after the first,
in order (spaghetti спагеті спагетті: the standard spelling, then VESUM's
non-standard one). A line starting with `+` adds candidates without taking
over: they come right after the usual first one (+he хє).

Wherever an alternative reads Latin g as г, a twin reading with ґ is offered
right after it (галактика, ґалактика), the 1928 convention for Latin g in
loanwords. It needs no lexicon entry of its own: its г twin must be a word.
An entry matches anywhere in a word, so endings and compounds work too
(chauffeurom шофером, nacguardia нацгвардія), and its readings rank first.
Endings attach to a stem made by dropping trailing vowels from both sides:
service сервіс → servic-, brigade бригада → brigad-, so servicu сервісу,
brigady бригади. Short entries (Xi, Mao) only match whole words.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


def is_cyrillic_consonant(c: str) -> bool:
    return len(c) == 1 and c in "БбВвГгҐґДдЖжЗзЙйКкЛлМмНнПпРрСсТтФфХхЦцЧчШшЩщ"


@dataclass(frozen=True)
class Rule:
    ctx: str  # "*", "C", "!C" or a set of characters
    latin: str  # may end with "$": end of word only
    cyrillic: str
    cost: int
    infinitive: bool = False  # cost `inf`: an infinitive ending
    loan: bool = False  # an entry of the loanword list
    loan_rank: int = 0  # position of this form on its loanword list line
    upturn: bool = False  # the ґ twin of a rule reading Latin g as г

    @property
    def key(self) -> str:
        return self.latin.removeprefix("^").removesuffix("$").removesuffix("/C").removesuffix("/V").removesuffix("/+")

    @property
    def at_start(self) -> bool:
        return self.latin.startswith("^")

    @property
    def before_vowel(self) -> bool:
        return self.latin.endswith("/V")

    @property
    def before_more(self) -> bool:
        return self.latin.endswith("/+")

    @property
    def before_consonant(self) -> bool:
        return self.latin.endswith("/C")

    @property
    def at_end(self) -> bool:
        return self.latin.endswith("$")

    def applies_after(self, prev: str) -> bool:
        match self.ctx:
            case "*": return True
            case "C": return is_cyrillic_consonant(prev)
            case "!C": return not is_cyrillic_consonant(prev)
            case chars: return prev != "" and prev in chars


@dataclass(frozen=True)
class Edge:
    length: int  # number of Latin characters consumed
    output: str  # already cased
    cost: int
    infinitive: bool = False
    loan: bool = False
    loan_rank: int = 0
    upturn: bool = False

    @property
    def plain(self) -> str:
        """The output with ґ read back as г, for lexicon lookups."""
        return self.output.replace("ґ", "г").replace("Ґ", "Г") if self.upturn else self.output


class Lexicon(Protocol):
    def contains(self, word: str) -> bool: ...
    def has_prefix(self, prefix: str) -> bool: ...
    # (frequency, proper only, variant only, infinitive)
    def entry(self, word: str) -> tuple[int, bool, bool, bool] | None: ...


class RuleTable:

    def __init__(self, rules: list[Rule], extras: dict[str, list[str]] | None = None):
        self.rules = rules
        self.extras = extras or {}  # `+latin cyrillic` lines: extra candidates for a whole word
        self.max_len = max((len(r.key) for r in rules), default=1)
        self._by_latin: dict[str, list[Rule]] = {}
        # More specific contexts first, so they win among native rules of equal length.
        for r in sorted(rules, key=lambda r: {"*": 2, "C": 1, "!C": 1}.get(r.ctx, 0)):
            self._by_latin.setdefault(r.key, []).append(r)

    @classmethod
    def load(cls, path: str | Path, loans: Iterable[str | Path] = ()) -> "RuleTable":
        """Load a rule table and loanword lists; a later list's entry replaces an earlier one's."""
        rules = []
        for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            fields = line.split()
            if len(fields) != 4:
                raise ValueError(f"{path}:{lineno}: expected `ctx latin cyrillic cost`")
            ctx, latin, cyrillic, cost = fields
            infinitive = cost == "inf"
            rules.append(Rule(ctx, latin, "" if cyrillic == "-" else cyrillic, 1 if infinitive else int(cost), infinitive))
        entries: dict[str, list[str]] = {}
        extras: dict[str, list[str]] = {}
        for loan_path in loans:
            if not Path(loan_path).exists():
                continue
            for lineno, line in enumerate(Path(loan_path).read_text(encoding="utf-8").splitlines(), 1):
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                fields = line.split()
                if len(fields) < 2:
                    raise ValueError(f"{loan_path}:{lineno}: expected `latin cyrillic [cyrillic…]`")
                if fields[0].startswith("+"):
                    extras[fields[0][1:].lower()] = fields[1:]
                else:
                    entries[fields[0].lower()] = fields[1:]
        for latin, forms in entries.items():
            for rank, cyrillic in enumerate(forms):
                if len(latin) < MIN_LOAN_IN_WORD:
                    rules.append(Rule("*", f"^{latin}$", cyrillic, 1, loan=True, loan_rank=rank))
                    continue
                rules.append(Rule("*", latin, cyrillic, 1, loan=True, loan_rank=rank))
                stem, cyrillic_stem = latin.rstrip(LATIN_VOWELS), cyrillic.rstrip(CYRILLIC_VOWELS)
                if stem != latin and len(stem) >= MIN_LOAN_IN_WORD and f"{stem}/+" not in entries:
                    rules.append(Rule("*", f"{stem}/+", cyrillic_stem, 1, loan=True, loan_rank=rank))
        # The ґ twin of every alternative reading Latin g as г.
        rules += [Rule(r.ctx, r.latin, r.cyrillic.replace("г", "ґ").replace("Г", "Ґ"), r.cost, r.infinitive,
                       r.loan, r.loan_rank, True)
                  for r in rules if r.cost > 0 and "g" in r.key and "г" in r.cyrillic.lower()]
        return cls(rules, extras)

    def _matching(self, word: str, i: int, prev: str):
        lower = word.lower()
        for n in range(min(self.max_len, len(word) - i), 0, -1):
            for r in self._by_latin.get(lower[i:i + n], ()):
                if (r.applies_after(prev) and (not r.at_end or i + n == len(word)) and (not r.at_start or i == 0)
                        and (not r.before_consonant or _is_consonant(lower[i + n:i + n + 1]))
                        and (not r.before_vowel or _is_vowel(lower[i + n:i + n + 1]))
                        and (not r.before_more or i + n < len(word))):
                    yield r

    def native_edge(self, word: str, i: int, prev: str, all_caps: bool) -> Edge:
        for r in self._matching(word, i, prev):
            if r.cost == 0:
                return Edge(len(r.key), _apply_case(r.cyrillic, word[i:i + len(r.key)], all_caps), 0)
        return Edge(1, word[i], 0)  # no rule: pass through

    def edges(self, word: str, i: int, prev: str, all_caps: bool) -> list[Edge]:
        """The native edge followed by every alternative edge at position i."""
        edges = [self.native_edge(word, i, prev, all_caps)]
        for r in self._matching(word, i, prev):
            if r.cost > 0:
                edges.append(Edge(len(r.key), _apply_case(r.cyrillic, word[i:i + len(r.key)], all_caps), r.cost,
                                  r.infinitive, r.loan, r.loan_rank, r.upturn))
        return edges

    def native(self, word: str, prev: str = "") -> str:
        all_caps = _is_all_caps(word)
        out, i = "", 0
        while i < len(word):
            e = self.native_edge(word, i, out[-1:] or prev, all_caps)
            out += e.output
            i += e.length
        return out

    def readings(self, word: str, lexicon: Lexicon, prev: str = "", limit: int = 9, max_cost: int = 8) -> list[str]:
        """Readings of `word`, best first, then the native reading.

        Real words rank by proper noun, then variant spelling, then tier
        (a whole word exactly as listed in the loanword list; a list entry
        with an ending or in a compound, or an infinitive reached through an
        infinitive ending; a native reading; alternative readings), then score: each
        alternative rule used costs one point, and frequency earns
        ln(frequency + 1) back. A word that is exactly a loanword list entry
        counts even if the lexicon doesn't know it; several forms listed for it
        come in their listed order. Proper nouns and
        abbreviations typed in lowercase are only offered after the native
        reading, capitalized, so they never replace an ordinary word.
        """
        all_caps = _is_all_caps(word)
        capitalized = word[:1].isupper()
        found: dict[str, tuple[bool, bool, int, float]] = {}
        names: dict[str, tuple[bool, int, float]] = {}  # proper nouns typed in lowercase

        def walk(i: int, out: str, plain: str, cost: int, infinitive: bool, loan: bool, whole_rank: int) -> None:
            # `plain` is `out` with ґ twins read as г: the form looked up in the lexicon.
            upturned = 0.001 if out != plain else 0  # a ґ twin comes right after its г reading
            if i == len(word):
                if whole_rank >= 0:  # exactly a listed word: beats stems and compounds, in listed order
                    key = (False, False, -1, whole_rank + (1000 if upturned else 0))  # ґ twins after all forms
                    found[out] = min(key, found.get(out, key))
                    return
                entry = lexicon.entry(plain.lower())
                if entry is None:
                    return
                freq, proper, variant, is_infinitive = entry
                if loan:
                    tier, proper = 0, False  # listed by the user, so never demoted as a name
                elif is_infinitive and infinitive:
                    tier = 0  # choditi -> ходити, biti -> бити beat the native ходіті, біті
                else:
                    tier = 1 if cost == 0 else 2
                score = cost - math.log(freq + 1) + upturned
                if proper and not capitalized:
                    name = out[:1].upper() + out[1:]
                    key = (variant, tier, score)
                    names[name] = min(key, names.get(name, key))
                else:
                    key = (proper, variant, tier, score)
                    found[out] = min(key, found.get(out, key))
                return
            for e in self.edges(word, i, out[-1:] or prev, all_caps):
                if cost + e.cost > max_cost:
                    continue
                nxt, nxt_plain = out + e.output, plain + e.plain
                if e.loan or lexicon.has_prefix(nxt_plain.lower()):
                    walk(i + e.length, nxt, nxt_plain, cost + e.cost, infinitive or e.infinitive, loan or e.loan,
                         e.loan_rank if e.loan and i == 0 and e.length == len(word) else -1)

        walk(0, "", "", 0, False, False, -1)
        ranked = sorted(found, key=found.__getitem__)
        native = self.native(word, prev)
        if native not in found:
            ranked.append(native)
        ranked += sorted((n for n in names if n not in found), key=names.__getitem__)
        for k, form in enumerate(self.extras.get(word.lower(), ()), 1):
            form = _apply_case(form, word, all_caps)
            if form in ranked:
                ranked.remove(form)
            ranked.insert(k, form)
        return ranked[:limit]


# Loanword entries shorter than this only match whole words (Xi, Mao), and
# stems must be at least this long, so they can't take over ordinary words.
MIN_LOAN_IN_WORD = 4
LATIN_VOWELS = "aeiouy"
CYRILLIC_VOWELS = "аеєиіїоуюя"


def _is_consonant(c: str) -> bool:
    """A Latin consonant letter; diacritic letters (č, š, ž) count too."""
    return c.isalpha() and c not in "aeiouyǎ"


def _is_vowel(c: str) -> bool:
    return c != "" and c in "aeiouyǎ"


def _is_all_caps(word: str) -> bool:
    letters = [c for c in word if c.isalpha()]
    return len(letters) > 1 and all(c.isupper() for c in letters)


def _apply_case(cyrillic: str, latin: str, all_caps: bool) -> str:
    """Case the output after the first letter of the consumed Latin span."""
    if all_caps:
        return cyrillic.upper()
    first = next((c for c in latin if c.isalpha()), "")
    if not first.isupper():
        return cyrillic
    for k, c in enumerate(cyrillic):
        if c.isalpha():
            return cyrillic[:k] + c.upper() + cyrillic[k + 1:]
    return cyrillic
