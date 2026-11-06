"""H3 Prompt Studio Database Connection Factory.

Normative Reference: specification-0.3.md §§5.7, 6.1
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Generator, Optional

from app.config import DB_PATH


def init_connection_pragmas(conn: sqlite3.Connection) -> None:
    """Apply mandatory PRAGMAs per specification §5.7 and §6.1:

    PRAGMA foreign_keys = ON;
    PRAGMA journal_mode = WAL;
    PRAGMA busy_timeout = 5000;
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.close()


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open a SQLite database connection with enforced PRAGMAs and Row factory."""
    target_path = db_path or DB_PATH
    conn = sqlite3.connect(str(target_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    init_connection_pragmas(conn)
    return conn


@contextmanager
def get_db(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding a SQLite connection, automatically closing on exit."""
    conn = get_db_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


# Alias for convenience
get_connection = get_db

