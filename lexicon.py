"""Cyrillic word forms, used to pick real words among transliteration readings.

Lexicons are SQLite databases (data/<lang>.db) with one table:

    words(word TEXT PRIMARY KEY, freq INTEGER, proper INTEGER, variant INTEGER, infinitive INTEGER) WITHOUT ROWID

Words are lowercase with apostrophes normalized to '. `proper` is 1 for words
known only as proper nouns or abbreviations (Бурян, БЮТ), which readings only
accept when typed with a capital. `variant` is 1 for words known only as
non-standard variant spellings (б'юджет), which rank after standard ones.
`infinitive` is 1 for verb infinitives (ходити). Build one with
tools/build_lexicon.py. Plain-text word lists
(`word<TAB>count<TAB>proper<TAB>variant<TAB>infinitive` per line, all but the
word optional) can also be loaded into memory, which the tests use.
"""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

APOSTROPHES = str.maketrans({"’": "'", "ʼ": "'", "`": "'"})

SCHEMA = ("CREATE TABLE IF NOT EXISTS words "
          "(word TEXT PRIMARY KEY, freq INTEGER NOT NULL, proper INTEGER NOT NULL DEFAULT 0, "
          "variant INTEGER NOT NULL DEFAULT 0, infinitive INTEGER NOT NULL DEFAULT 0) WITHOUT ROWID")

FLAGS = ("proper", "variant", "infinitive")


def normalize(word: str) -> str:
    return word.translate(APOSTROPHES).lower()


class Lexicon:

    _CACHE_LIMIT = 100_000

    def __init__(self, entries: Iterable[tuple[str, int, bool, bool, bool]] = (), *,
                 db: sqlite3.Connection | None = None):
        if db is None:
            db = sqlite3.connect(":memory:")
            db.execute(SCHEMA)
            db.executemany(
                "INSERT INTO words VALUES (?, ?, ?, ?, ?) ON CONFLICT(word) DO UPDATE SET "
                "freq = freq + excluded.freq, proper = proper AND excluded.proper, "
                "variant = variant AND excluded.variant, infinitive = infinitive OR excluded.infinitive",
                ((normalize(w), c, int(p), int(v), int(i)) for w, c, p, v, i in entries),
            )
        self._db = db
        # Databases built before a flag existed lack its column; read it as 0.
        columns = {row[1] for row in db.execute("PRAGMA table_info(words)")}
        flags = ", ".join(f if f in columns else "0" for f in FLAGS)
        self._entry_sql = f"SELECT freq, {flags} FROM words WHERE word = ?"
        self._prefix_cache: dict[str, bool] = {}

    @classmethod
    def load(cls, path: str | Path) -> "Lexicon":
        """Open a .db lexicon (or read a .words text list); a missing file gives an empty lexicon."""
        path = Path(path)
        if not path.exists():
            return cls()
        if path.suffix == ".words":
            return cls(_read_words(path))
        return cls(db=sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True))

    def __len__(self) -> int:
        return self._db.execute("SELECT count(*) FROM words").fetchone()[0]

    def contains(self, word: str) -> bool:
        return self._db.execute("SELECT 1 FROM words WHERE word = ?", (word,)).fetchone() is not None

    def has_prefix(self, prefix: str) -> bool:
        if not prefix:
            return True
        cached = self._prefix_cache.get(prefix)
        if cached is None:
            # Every word starting with `prefix` sorts in [prefix, prefix with its last character incremented).
            upper = prefix[:-1] + chr(ord(prefix[-1]) + 1)
            row = self._db.execute("SELECT 1 FROM words WHERE word >= ? AND word < ? LIMIT 1", (prefix, upper)).fetchone()
            cached = row is not None
            if len(self._prefix_cache) >= self._CACHE_LIMIT:
                self._prefix_cache.clear()
            self._prefix_cache[prefix] = cached
        return cached

    def freq(self, word: str) -> int:
        entry = self.entry(word)
        return entry[0] if entry else 0

    def entry(self, word: str) -> tuple[int, bool, bool, bool] | None:
        """(frequency, proper noun only, variant spelling only, infinitive), or None for unknown words."""
        row = self._db.execute(self._entry_sql, (word,)).fetchone()
        return (row[0], bool(row[1]), bool(row[2]), bool(row[3])) if row else None


def _read_words(path: Path) -> Iterable[tuple[str, int, bool, bool, bool]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            word, count, proper, variant, infinitive = (line.rstrip("\n").split("\t") + [""] * 4)[:5]
            if word:
                yield word, int(count) if count else 0, proper == "1", variant == "1", infinitive == "1"
