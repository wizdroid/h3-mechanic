"""H3 Prompt Studio Database Migration Runner.

Normative Reference: specification-0.3.md §5.7
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
import shutil
import sqlite3
from typing import List, Optional, Tuple

from app.config import BACKUPS_DIR, DB_PATH, MIGRATIONS_DIR
from app.storage.db import get_db_connection

logger = logging.getLogger(__name__)


def create_pre_migration_backup(db_path: Path) -> Optional[Path]:
    """Save a copy of the database before applying migrations per §5.7:

    data/backups/h3studio-pre-migration-<ts>.db
    """
    if not db_path.exists() or db_path.stat().st_size == 0:
        return None

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup_path = BACKUPS_DIR / f"h3studio-pre-migration-{ts}.db"

    # Use SQLite vacuum into or copy while connection is not active
    # For file safety, copy the raw file
    shutil.copy2(db_path, backup_path)
    logger.info("Created pre-migration database snapshot at %s", backup_path)
    return backup_path


def parse_migration_version(filename: str) -> Optional[int]:
    """Extract integer version from migration file (e.g. '0001_initial.sql' -> 1)."""
    match = re.match(r"^(\d{4})_.*\.sql$", filename)
    if match:
        return int(match.group(1))
    return None


def get_available_migrations(migrations_dir: Path) -> List[Tuple[int, Path]]:
    """Return sorted list of (version, file_path) available in migrations directory."""
    if not migrations_dir.exists():
        return []

    migrations: List[Tuple[int, Path]] = []
    for file_path in sorted(migrations_dir.glob("*.sql")):
        ver = parse_migration_version(file_path.name)
        if ver is not None:
            migrations.append((ver, file_path))

    migrations.sort(key=lambda x: x[0])
    return migrations


def get_current_schema_version(conn: sqlite3.Connection) -> int:
    """Read the current schema version from schema_version table (0 if uninitialized)."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';"
        )
        if not cursor.fetchone():
            return 0

        cursor.execute("SELECT MAX(version) FROM schema_version;")
        row = cursor.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return 0
    finally:
        cursor.close()


def run_migrations(
    db_path: Optional[Path] = None,
    migrations_dir: Optional[Path] = None,
) -> int:
    """Apply forward-only migrations inside transactions per §5.7.

    Aborts startup if on-disk schema_version is higher than known migrations.
    Returns the latest applied schema version integer.
    """
    target_db = db_path or DB_PATH
    target_migrations = migrations_dir or MIGRATIONS_DIR

    target_db.parent.mkdir(parents=True, exist_ok=True)
    available = get_available_migrations(target_migrations)
    max_known_version = available[-1][0] if available else 0

    # Check existing schema version first
    conn = get_db_connection(target_db)
    current_version = get_current_schema_version(conn)

    if current_version > max_known_version:
        conn.close()
        raise RuntimeError(
            f"Database schema version ({current_version}) is newer than known migrations ({max_known_version}). "
            "Startup aborted to prevent data corruption."
        )

    # Determine pending migrations
    pending = [(ver, path) for ver, path in available if ver > current_version]
    if not pending:
        conn.close()
        return current_version

    # Make pre-migration backup before touching the database
    create_pre_migration_backup(target_db)

    try:
        for ver, script_path in pending:
            sql_text = script_path.read_text(encoding="utf-8")
            cursor = conn.cursor()
            # Execute migration script in transaction
            conn.execute("BEGIN TRANSACTION;")
            conn.executescript(sql_text)
            applied_at = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?);",
                (ver, applied_at),
            )
            conn.commit()
            logger.info("Applied migration %04d (%s)", ver, script_path.name)
        current_version = get_current_schema_version(conn)
    except Exception as exc:
        conn.rollback()
        logger.error("Migration failed: %s", exc)
        raise
    finally:
        conn.close()

    return current_version
