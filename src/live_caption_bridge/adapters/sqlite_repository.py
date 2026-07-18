import sqlite3
import time
from pathlib import Path


class SQLiteRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS captions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original TEXT NOT NULL,
                translated TEXT,
                source_lang TEXT NOT NULL,
                target_lang TEXT,
                started_ns INTEGER NOT NULL,
                ended_ns INTEGER NOT NULL,
                created_ns INTEGER NOT NULL
            )"""
        )
        self._conn.commit()

    def save(
        self,
        original: str,
        translated: str | None,
        source_lang: str,
        target_lang: str | None,
        started_ns: int,
        ended_ns: int,
    ) -> int:
        now = time.monotonic_ns()
        cur = self._conn.execute(
            """INSERT INTO captions
               (original, translated, source_lang, target_lang,
                started_ns, ended_ns, created_ns)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (original, translated, source_lang, target_lang,
             started_ns, ended_ns, now),
        )
        self._conn.commit()
        return cur.lastrowid # type: ignore

    def close(self) -> None:
        self._conn.close()
