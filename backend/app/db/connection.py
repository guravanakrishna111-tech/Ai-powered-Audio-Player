import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable

from app.config import settings


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        settings.artwork_dir.mkdir(parents=True, exist_ok=True)
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        schema_path = Path(__file__).parent / "schema.sql"
        with self.connection() as conn:
            conn.executescript(schema_path.read_text(encoding="utf-8"))
            conn.commit()

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.connection() as conn:
            cur = conn.execute(sql, tuple(params))
            conn.commit()
            return cur

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self.connection() as conn:
            return conn.execute(sql, tuple(params)).fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(sql, tuple(params)).fetchall()


class LazyDatabase:
    """Proxy that creates the SQLite database only when first used.

    Import-time side effects make tests brittle and can also fail before the
    application has a chance to configure its data directory. Delaying the real
    database initialization keeps imports cheap while preserving the same API.
    """

    def __init__(self) -> None:
        self._database: Database | None = None

    def _get_database(self) -> Database:
        if self._database is None:
            self._database = Database()
        return self._database

    def __getattr__(self, item: str) -> Any:
        return getattr(self._get_database(), item)


db = LazyDatabase()
