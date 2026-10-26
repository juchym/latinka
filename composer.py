"""Word composer: the API the IME front ends (fcitx5, IBus, terminal) use.

Latin letters and apostrophes are buffered into a word; `candidates()` gives
its Cyrillic readings, best first, followed by the Latin text as typed. Front
ends commit one at a word boundary.
"""

import os
import re
import unicodedata
from functools import cache
from pathlib import Path

from lexicon import Lexicon
from rules import RuleTable, is_cyrillic_consonant

DATA = Path(__file__).parent / "data"

# The user's own loanword list, read after the installed one and overriding it.
USER_DATA = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "udnc"

# Letters that aren't words, so the lexicon never offers them.
SINGLE_LETTERS: dict[str, tuple[str, ...]] = {}

# Laughter (haha, ahah, ahahhaha, hihihi): only vowels and h, with at least two runs of h.
# Its h is х, not the native г, and it can be any length, so no lexicon lists it.
# A single aha stays ага.
LAUGHTER = re.compile(r"[aeiouy]*(?:h+[aeiouy]+)+h*|[aeiouy]+h+", re.IGNORECASE)
H_RUN = re.compile(r"h+", re.IGNORECASE)


def is_word_char(c: str) -> bool:
    """A Latin letter (with or without diacritics) or an apostrophe."""
    return len(c) == 1 and (c == "'" or c.isalpha() and unicodedata.name(c, "").startswith("LATIN"))


# Hushing (Composer.hush): a háček on c, s or z before the cursor (č, š, ž), or on both
# letters of st (šť, which is щ). It never makes a soft sign. Front ends trigger it with x
# right after those letters (sx → š, stx → šť), where x can't mean кс, or a tap of AltGr.
HUSH_KEY = "x"


def is_hush_key(ch: str) -> bool:
    return ch.lower() == HUSH_KEY
HUSH = {"c": "č", "s": "š", "z": "ž", "C": "Č", "S": "Š", "Z": "Ž"}
HUSH_AFTER_S = {"t": "ť", "T": "Ť"}


def _table(lang: str) -> RuleTable:
    """The rule table, reloaded when the user's loanword list changes."""
    user_loans = USER_DATA / f"{lang}.loans"
    try:
        mtime = user_loans.stat().st_mtime
    except OSError:
        mtime = None
    return _load_table(lang, mtime)


@cache
def _load_table(lang: str, user_loans_mtime: float | None) -> RuleTable:
    return RuleTable.load(DATA / f"{lang}.rules", [DATA / f"{lang}.loans", USER_DATA / f"{lang}.loans"])


@cache
def _lexicon(lang: str) -> Lexicon:
    return Lexicon.load(DATA / f"{lang}.db")


class Composer:

    def __init__(self, lang: str, lexicon: Lexicon | None = None):
        self._lang = lang
        self._lexicon_override = lexicon
        self._buf = ""
        self._cursor = 0  # position in the buffer, in characters
        self._prev = ""
        self._candidates: list[str] | None = None
        self._latin = False  # Latin mode: the last word was committed as Latin, so Latin comes first

    @property
    def _lexicon(self) -> Lexicon:
        # Loaded on first use, so starting the IME stays fast.
        return self._lexicon_override if self._lexicon_override is not None else _lexicon(self._lang)

    def set_context(self, prev: str) -> None:
        """The character before the word (from surrounding text), if known."""
        self._prev = prev[-1:]
        self._candidates = None

    def push(self, ch: str) -> None:
        """Insert at the cursor."""
        self._buf = self._buf[:self._cursor] + ch + self._buf[self._cursor:]
        self._cursor += len(ch)
        self._candidates = None

    def can_hush(self) -> bool:
        """Whether hush() would change the letters before the cursor (c, s, z, or st)."""
        before = self._buf[max(0, self._cursor - 2):self._cursor]
        return before[-1:] in HUSH or (len(before) == 2 and before[0] in "sSšŠ" and before[1] in HUSH_AFTER_S)

    def hush(self) -> None:
        """Make the letter before the cursor hushing: c → č, s → š, z → ž, st → šť."""
        if not self.can_hush():
            return
        before = self._buf[self._cursor - 1]
        if before in HUSH:
            marked, start = HUSH[before], self._cursor - 1
        else:  # st → šť
            s = self._buf[self._cursor - 2]
            marked, start = HUSH.get(s, s) + HUSH_AFTER_S[before], self._cursor - 2
        self._buf = self._buf[:start] + marked + self._buf[self._cursor:]
        self._candidates = None

    def pop(self) -> None:
        """Delete the character before the cursor (Backspace)."""
        if self._cursor > 0:
            self._buf = self._buf[:self._cursor - 1] + self._buf[self._cursor:]
            self._cursor -= 1
            self._candidates = None

    def delete(self) -> None:
        """Delete the character after the cursor (Delete)."""
        if self._cursor < len(self._buf):
            self._buf = self._buf[:self._cursor] + self._buf[self._cursor + 1:]
            self._candidates = None

    def move(self, delta: int) -> None:
        self._cursor = max(0, min(len(self._buf), self._cursor + delta))

    def move_to(self, position: int) -> None:
        """Move the cursor to a position; -1 is the end."""
        self._cursor = len(self._buf) if position < 0 else max(0, min(len(self._buf), position))

    def cursor(self) -> int:
        return self._cursor

    def raw(self) -> str:
        return self._buf

    def commit(self, text: str) -> None:
        """Note what was committed for the current word, then clear it.

        Committing the Latin text as typed switches to Latin mode, where Latin comes first;
        committing a Cyrillic reading switches back.
        """
        # Only a deliberate choice changes the mode: the Latin text, or another candidate than the default.
        if self._buf and (text == self._buf or text != self.candidates()[0]):
            self._latin = text == self._buf
        self.clear()

    def clear(self) -> None:
        self._buf = ""
        self._cursor = 0
        self._prev = ""
        self._candidates = None

    def candidates(self) -> list[str]:
        if not self._buf:
            return []
        if self._candidates is None:
            table = _table(self._lang)
            readings = table.readings(self._buf, self._lexicon, self._prev)
            # A word starting with j may continue existing text: offer the native reading for the
            # other context too, й after a consonant or ь otherwise (jsja: йся, ься).
            # When the best reading is a word and the other isn't (jogo: його), the other goes last.
            if self._buf[:1] in ("j", "J"):
                other = table.native(self._buf, "" if is_cyrillic_consonant(self._prev) else "н")
                if other not in readings:
                    if self._lexicon.entry(readings[0].lower()) and not self._lexicon.entry(other.lower()):
                        readings.append(other)
                    else:
                        readings.insert(1, other)
            # Single letters go right after the first reading, before one-letter names.
            letters = [l.upper() if self._buf.isupper() else l for l in SINGLE_LETTERS.get(self._buf.lower(), ())]
            for k, letter in enumerate((l for l in letters if l != readings[0]), 1):
                if letter in readings:
                    readings.remove(letter)
                readings.insert(k, letter)
            if LAUGHTER.fullmatch(self._buf) and len(H_RUN.findall(self._buf)) >= 2:
                laugh = table.native(self._buf.replace("h", "ch").replace("H", "Ch"), self._prev)
                # With e, є forms come right after (хехе, хєхє); an initial e varies on its own
                # (ехехе, ехєхє, єхєхє, єхехе).
                def upturn(text: str) -> str:
                    return text.replace("е", "є").replace("Е", "Є")
                head, body = (laugh[:1], laugh[1:]) if laugh[:1] in ("е", "Е") else ("", laugh)
                laughs = [head + body, head + upturn(body), upturn(head) + upturn(body), upturn(head) + body]
                laughs = list(dict.fromkeys(laughs))  # drop duplicates, keep the order
                for k, form in enumerate(laughs):
                    if form in readings:
                        readings.remove(form)
                    readings.insert(k, form)
            self._candidates = readings + [self._buf] if self._buf not in readings else readings
            if self._latin:  # Latin mode: the Latin text first
                self._candidates = [self._buf] + [r for r in self._candidates if r != self._buf]
        return self._candidates


def transliterate(text: str, lang: str, lexicon: Lexicon | None = None) -> str:
    """Transliterate a whole text, taking the best reading of every word."""
    c = Composer(lang, lexicon)
    out = []
    for ch in text + " ":
        if is_hush_key(ch) and c.raw() and c.can_hush():
            c.hush()
            continue
        if is_word_char(ch):
            if not c.raw():
                c.set_context(out[-1][-1:] if out else "")
            c.push(ch)
            continue
        if c.raw():
            out.append(c.candidates()[0])
            c.clear()
        out.append(ch)
    return "".join(out)[:-1]
