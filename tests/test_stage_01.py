"""Tests for Stage 01: Core Scaffolding, Storage & Health Endpoint.

Normative Reference: specification-0.3.md §§5.1, 5.6, 5.6.1, 5.7, 6.1, 17.1, 17.2
Acceptance Criteria: A-20, A-35, A-48, A-49
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import (
    ALLOWED_HOST,
    DEFAULT_PORT,
    SPECIFICATION_VERSION,
    resolve_listen_port,
    verify_host,
)
from app.main import app
from app.storage.db import get_db_connection, init_connection_pragmas
from app.storage.migration_runner import (
    create_pre_migration_backup,
    get_current_schema_version,
    run_migrations,
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Ensure clean test environment for config and temporary database."""
    monkeypatch.delenv("H3_PORT", raising=False)
    monkeypatch.delenv("H3_HOST", raising=False)


# ==============================================================================
# 1. Storage & PRAGMA Verification Tests
# ==============================================================================

def test_database_pragmas_enforced(tmp_path: Path):
    """Verify that PRAGMAs (foreign_keys=ON, WAL, busy_timeout=5000) are enforced per §6.1."""
    test_db = tmp_path / "test_pragmas.db"
    conn = get_db_connection(test_db)
    cursor = conn.cursor()

    # foreign_keys
    cursor.execute("PRAGMA foreign_keys;")
    assert cursor.fetchone()[0] == 1, "foreign_keys PRAGMA must be 1 (ON)"

    # journal_mode
    cursor.execute("PRAGMA journal_mode;")
    assert cursor.fetchone()[0].lower() == "wal", "journal_mode must be WAL"

    # busy_timeout
    cursor.execute("PRAGMA busy_timeout;")
    assert cursor.fetchone()[0] == 5000, "busy_timeout must be 5000"

    conn.close()


def test_schema_tables_and_indexes_exist(tmp_path: Path):
    """Verify that all tables and indexes defined in Section 6.1 are created."""
    test_db = tmp_path / "test_schema.db"
    run_migrations(db_path=test_db)

    conn = get_db_connection(test_db)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        "schema_version",
        "projects",
        "clips",
        "references_tokens",
        "subjects",
        "shots",
        "subject_pictures",
        "speakers",
        "dialogue_lines",
        "onscreen_texts",
        "retention_markers",
        "prompts",
        "settings",
    }
    missing_tables = expected_tables - tables
    assert not missing_tables, f"Missing tables in schema: {missing_tables}"

    # Verify indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = {row[0] for row in cursor.fetchall()}
    expected_indexes = {
        "idx_references_clip",
        "idx_shots_clip",
        "idx_lines_clip",
        "idx_prompts_clip",
        "idx_subject_pictures_subject",
        "idx_speakers_clip",
        "idx_onscreen_clip",
        "idx_retention_clip",
    }
    missing_indexes = expected_indexes - indexes
    assert not missing_indexes, f"Missing indexes in schema: {missing_indexes}"

    conn.close()


def test_foreign_key_cascades(tmp_path: Path):
    """Verify foreign key ON DELETE CASCADE behavior per Section 6.1."""
    test_db = tmp_path / "test_cascades.db"
    run_migrations(db_path=test_db)

    conn = get_db_connection(test_db)
    cursor = conn.cursor()

    # Create project
    cursor.execute(
        "INSERT INTO projects (name, created_at, updated_at) VALUES ('Proj1', '2026-01-01', '2026-01-01');"
    )
    proj_id = cursor.lastrowid

    # Create clip
    cursor.execute(
        """
        INSERT INTO clips (
            project_id, mode, h3_model, duration_s, resolution, ratio, created_at, updated_at
        ) VALUES (?, 'T2VA', 'MiniMax-H3', 8, '768P', '16:9', '2026-01-01', '2026-01-01');
        """,
        (proj_id,),
    )
    clip_id = cursor.lastrowid

    # Create shot
    cursor.execute(
        """
        INSERT INTO shots (clip_id, ordinal, start_ms, end_ms, created_at, updated_at)
        VALUES (?, 1, 0, 8000, '2026-01-01', '2026-01-01');
        """,
        (clip_id,),
    )

    # Create speaker
    cursor.execute(
        """
        INSERT INTO speakers (clip_id, display_name, created_at, updated_at)
        VALUES (?, 'Officer', '2026-01-01', '2026-01-01');
        """,
        (clip_id,),
    )
    speaker_id = cursor.lastrowid

    # Create dialogue line
    cursor.execute(
        """
        INSERT INTO dialogue_lines (
            clip_id, speaker_id, language, text_raw, created_at, updated_at
        ) VALUES (?, ?, 'English', 'Hello.', '2026-01-01', '2026-01-01');
        """,
        (clip_id, speaker_id),
    )
    conn.commit()

    # Deleting project must cascade delete clips, shots, speakers, lines
    cursor.execute("DELETE FROM projects WHERE id = ?;", (proj_id,))
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM clips WHERE id = ?;", (clip_id,))
    assert cursor.fetchone()[0] == 0, "Clip was not cascade deleted"

    cursor.execute("SELECT COUNT(*) FROM shots WHERE clip_id = ?;", (clip_id,))
    assert cursor.fetchone()[0] == 0, "Shot was not cascade deleted"

    cursor.execute("SELECT COUNT(*) FROM speakers WHERE clip_id = ?;", (clip_id,))
    assert cursor.fetchone()[0] == 0, "Speaker was not cascade deleted"

    cursor.execute("SELECT COUNT(*) FROM dialogue_lines WHERE clip_id = ?;", (clip_id,))
    assert cursor.fetchone()[0] == 0, "Dialogue line was not cascade deleted"

    conn.close()


def test_schema_check_constraints(tmp_path: Path):
    """Verify CHECK constraints in schema per Section 6.1."""
    test_db = tmp_path / "test_checks.db"
    run_migrations(db_path=test_db)

    conn = get_db_connection(test_db)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO projects (name, created_at, updated_at) VALUES ('P1', '2026-01-01', '2026-01-01');"
    )
    proj_id = cursor.lastrowid

    # 1. Invalid duration for MiniMax-H3 (duration 3 is illegal)
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO clips (
                project_id, mode, h3_model, duration_s, resolution, ratio, created_at, updated_at
            ) VALUES (?, 'T2VA', 'MiniMax-H3', 3, '768P', '16:9', '2026-01-01', '2026-01-01');
            """,
            (proj_id,),
        )

    # 2. Invalid resolution for MiniMax-H3-Max (2K is illegal for Max)
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO clips (
                project_id, mode, h3_model, duration_s, resolution, ratio, created_at, updated_at
            ) VALUES (?, 'T2VA', 'MiniMax-H3-Max', 6, '2K', '16:9', '2026-01-01', '2026-01-01');
            """,
            (proj_id,),
        )

    # 3. T2VA ratio cannot be adaptive
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO clips (
                project_id, mode, h3_model, duration_s, resolution, ratio, created_at, updated_at
            ) VALUES (?, 'T2VA', 'MiniMax-H3', 8, '768P', 'adaptive', '2026-01-01', '2026-01-01');
            """,
            (proj_id,),
        )

    # Insert a valid clip
    cursor.execute(
        """
        INSERT INTO clips (
            project_id, mode, h3_model, duration_s, resolution, ratio, created_at, updated_at
        ) VALUES (?, 'REF2VA', 'MiniMax-H3', 8, '768P', '16:9', '2026-01-01', '2026-01-01');
        """,
        (proj_id,),
    )
    valid_clip_id = cursor.lastrowid

    # 4. references_tokens: width_px <= 0 rejected
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO references_tokens (
                clip_id, kind, ordinal, caption, position, width_px, created_at, updated_at
            ) VALUES (?, 'image', 1, 'cap', 1, 0, '2026-01-01', '2026-01-01');
            """,
            (valid_clip_id,),
        )

    # 5. references_tokens: duration_ms outside 2000..15000 rejected for audio
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO references_tokens (
                clip_id, kind, ordinal, caption, position, duration_ms, created_at, updated_at
            ) VALUES (?, 'audio', 1, 'cap', 1, 1999, '2026-01-01', '2026-01-01');
            """,
            (valid_clip_id,),
        )

    # 6. subjects: invalid pronoun rejected
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO subjects (
                clip_id, ordinal, role, pronoun, created_at, updated_at
            ) VALUES (?, 1, 'person', 'their', '2026-01-01', '2026-01-01');
            """,
            (valid_clip_id,),
        )

    conn.close()


# ==============================================================================
# 2. Migration Engine & Snapshot Backup Tests
# ==============================================================================

def test_migration_runner_snapshot_backup(tmp_path: Path):
    """Verify that pre-migration backup is created before applying migrations (§5.7)."""
    test_db = tmp_path / "test_backup.db"
    run_migrations(db_path=test_db)
    assert test_db.exists()

    # Modify DB so it has data
    conn = get_db_connection(test_db)
    conn.execute("INSERT INTO settings (key, value) VALUES ('k1', 'v1');")
    conn.commit()
    conn.close()

    backup = create_pre_migration_backup(test_db)
    assert backup is not None
    assert backup.exists()
    assert backup.stat().st_size > 0
    assert "h3studio-pre-migration-" in backup.name


def test_newer_schema_version_aborts_startup(tmp_path: Path):
    """Verify that opening a DB with newer schema_version than known aborts startup (§5.7)."""
    test_db = tmp_path / "test_future.db"
    run_migrations(db_path=test_db)

    # Manually inject higher version
    conn = get_db_connection(test_db)
    conn.execute("UPDATE schema_version SET version = 9999;")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="newer than known migrations"):
        run_migrations(db_path=test_db)


# ==============================================================================
# 3. Configuration, Host & Port Resolution Tests
# ==============================================================================

def test_port_resolution_default(tmp_path: Path):
    """Verify default port is 9013 when no env var or settings row exists."""
    test_db = tmp_path / "empty_settings.db"
    run_migrations(db_path=test_db)
    port = resolve_listen_port(db_path=test_db)
    assert port == DEFAULT_PORT == 9013


def test_port_resolution_from_env(monkeypatch: pytest.MonkeyPatch):
    """Verify H3_PORT environment variable wins in resolution chain (§5.7)."""
    monkeypatch.setenv("H3_PORT", " 9050 ")
    port = resolve_listen_port()
    assert port == 9050


def test_port_resolution_invalid_env_aborts(monkeypatch: pytest.MonkeyPatch):
    """Verify invalid H3_PORT aborts startup with clear error (§5.7)."""
    monkeypatch.setenv("H3_PORT", "abc")
    with pytest.raises(ValueError, match="Invalid H3_PORT"):
        resolve_listen_port()

    monkeypatch.setenv("H3_PORT", "70000")
    with pytest.raises(ValueError, match="Invalid H3_PORT"):
        resolve_listen_port()


def test_port_resolution_from_settings(tmp_path: Path):
    """Verify database settings table 'listen_port' is respected when H3_PORT is unset."""
    test_db = tmp_path / "settings_port.db"
    run_migrations(db_path=test_db)

    conn = get_db_connection(test_db)
    conn.execute("INSERT INTO settings (key, value) VALUES ('listen_port', '9025');")
    conn.commit()
    conn.close()

    port = resolve_listen_port(db_path=test_db)
    assert port == 9025


def test_host_verification_loopback(monkeypatch: pytest.MonkeyPatch):
    """Verify that H3_HOST must be 127.0.0.1 (§5.7)."""
    monkeypatch.setenv("H3_HOST", "127.0.0.1")
    assert verify_host() == "127.0.0.1"

    monkeypatch.setenv("H3_HOST", "0.0.0.0")
    with pytest.raises(ValueError, match="only loopback '127.0.0.1' is permitted"):
        verify_host()


# ==============================================================================
# 4. Security Middleware & Health Endpoint Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_security_middleware_host_blocking():
    """Verify that requests with non-loopback Host header are rejected with 403 (Criterion A-35)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # Valid loopback host
        resp = await client.get("/api/health", headers={"Host": "127.0.0.1:9013"})
        assert resp.status_code == 200

        # Valid localhost
        resp = await client.get("/api/health", headers={"Host": "localhost:9013"})
        assert resp.status_code == 200

        # Foreign host must be blocked with 403
        resp = await client.get("/api/health", headers={"Host": "evil.com"})
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_security_middleware_origin_validation():
    """Verify that mutating requests with foreign Origin header are rejected with 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # Foreign Origin on POST/PUT
        resp = await client.post(
            "/api/health",
            headers={"Host": "127.0.0.1:9013", "Origin": "http://evil.com"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "forbidden"

        # Valid Origin
        resp = await client.post(
            "/api/health",
            headers={"Host": "127.0.0.1:9013", "Origin": "http://127.0.0.1:9013"},
        )
        # /api/health only has GET, so method not allowed 405 means it passed security middleware
        assert resp.status_code == 405


@pytest.mark.asyncio
async def test_health_endpoint_response_structure():
    """Verify GET /api/health structure per §5.6.1 and Criterion A-48."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        resp = await client.get("/api/health", headers={"Host": "127.0.0.1:9013"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "ok"
        assert data["specification_version"] == "0.3"
        assert data["schema_version"] == 1
        assert data["ollama"] in ("reachable", "unreachable")
        assert isinstance(data["model_count"], int)
        assert data["bind"].startswith("127.0.0.1:")
