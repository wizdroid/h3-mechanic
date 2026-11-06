"""H3 Prompt Studio Configuration and Path Resolution.

Normative Reference: specification-0.3.md §§5.1, 5.7, 17.1, 17.2
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
from typing import Optional

# Absolute repository root
REPO_ROOT = Path("/home/wizdroid/Applications/h3-mechanic").resolve()

# Designate runtime data directories under <repo>/data/
DATA_DIR = REPO_ROOT / "data"
EXPORTS_DIR = DATA_DIR / "exports"
BACKUPS_DIR = DATA_DIR / "backups"
LOGS_DIR = DATA_DIR / "logs"

# Primary database path
DB_PATH = DATA_DIR / "h3studio.db"

# Migrations directory
MIGRATIONS_DIR = REPO_ROOT / "app" / "storage" / "migrations"

# Specification metadata
SPECIFICATION_VERSION = "0.3"
DEFAULT_PORT = 9013
ALLOWED_HOST = "127.0.0.1"


def ensure_directories() -> None:
    """Create data, exports, backups, and logs directories if not existing."""
    for directory in (DATA_DIR, EXPORTS_DIR, BACKUPS_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def verify_host() -> str:
    """Verify that H3_HOST is set to loopback 127.0.0.1 only.

    Per §5.7: H3_HOST, if set, must be 127.0.0.1; any other value aborts startup.
    """
    host = os.environ.get("H3_HOST", ALLOWED_HOST).strip()
    if host != ALLOWED_HOST:
        raise ValueError(
            f"Invalid H3_HOST '{host}': only loopback '127.0.0.1' is permitted."
        )
    return host


def resolve_listen_port(db_path: Optional[Path] = None) -> int:
    """Resolve listen port according to specification-0.3.md §5.7:

    Resolution order:
    1. H3_PORT environment variable (must be integer 1–65535).
    2. settings table 'listen_port' value (if valid integer 1–65535).
    3. Default: 9013.
    """
    env_port = os.environ.get("H3_PORT")
    if env_port is not None:
        stripped = env_port.strip()
        if not stripped:
            raise ValueError("H3_PORT environment variable is set but empty.")
        try:
            port = int(stripped)
            if not (1 <= port <= 65535):
                raise ValueError
            return port
        except ValueError:
            raise ValueError(
                f"Invalid H3_PORT '{env_port}': must be an integer between 1 and 65535."
            )

    target_db = db_path or DB_PATH
    if target_db.exists() and target_db.stat().st_size > 0:
        try:
            conn = sqlite3.connect(str(target_db), timeout=2.0)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM settings WHERE key = 'listen_port';"
            )
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                port_val = int(str(row[0]).strip())
                if 1 <= port_val <= 65535:
                    return port_val
        except Exception:
            # Fall through if table does not exist yet or DB locked
            pass

    return DEFAULT_PORT
