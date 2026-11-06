"""Frame Modes (I2VA, FL2VA, L2VA) Backend Routes & Reference Tokens Manager (§4.4.3–§4.4.5, §5.6, §7.3).

Provides:
- GET /api/clips/{clip_id}/references: List references in position order
- POST /api/clips/{clip_id}/references: Add image/video/audio reference token
- PUT /api/clips/{clip_id}/references/{ref_id}: Update reference token
- DELETE /api/clips/{clip_id}/references/{ref_id}: Remove reference token and re-derive ordinals
- GET /api/clips/{clip_id}/instruction-preview: Pre-generation instruction line preview (§4.4.4, Criterion A-06)
"""

from __future__ import annotations
from datetime import datetime, timezone
import logging
import sqlite3
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.storage.db import get_connection
from app.engine.renderer import build_instruction_line

logger = logging.getLogger("h3studio.frame_routes")
router = APIRouter(prefix="/api", tags=["frame_modes"])


class ReferenceCreate(BaseModel):
    kind: str = "image"
    caption: Optional[str] = ""
    role_hint: Optional[str] = ""
    source_file: Optional[str] = ""
    plate_filename: Optional[str] = ""
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    duration_ms: Optional[int] = None


class ReferenceUpdate(BaseModel):
    caption: Optional[str] = None
    role_hint: Optional[str] = None
    source_file: Optional[str] = None
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    duration_ms: Optional[int] = None


def _resequence_reference_tokens(cur: sqlite3.Cursor, clip_id: int) -> None:
    """
    Re-sequence positions 1..N and ordinals 1..K per kind (§6.4).
    Uses a temporary positive offset (+1000000) to avoid SQLite UNIQUE constraint collisions.
    """
    # 1. Temporary shift
    cur.execute("UPDATE references_tokens SET position = position + 1000000, ordinal = ordinal + 1000000 WHERE clip_id = ?", (clip_id,))

    # 2. Fetch all in original position order
    cur.execute("SELECT id, kind FROM references_tokens WHERE clip_id = ? ORDER BY position ASC, id ASC", (clip_id,))
    rows = cur.fetchall()

    kind_counters: dict[str, int] = {}
    for pos_idx, r in enumerate(rows, start=1):
        rid = r["id"]
        k = r["kind"]
        kind_counters[k] = kind_counters.get(k, 0) + 1
        ord_val = kind_counters[k]

        cur.execute(
            "UPDATE references_tokens SET position = ?, ordinal = ? WHERE id = ?",
            (pos_idx, ord_val, rid),
        )


@router.get("/clips/{clip_id}/references")
def list_reference_tokens(clip_id: int) -> list[dict[str, Any]]:
    """GET /api/clips/{id}/references - list reference tokens for a clip."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM references_tokens WHERE clip_id = ? ORDER BY position ASC", (clip_id,))
        return [dict(r) for r in cur.fetchall()]


@router.post("/clips/{clip_id}/references")
def create_reference_token(clip_id: int, ref_in: ReferenceCreate) -> dict[str, Any]:
    """
    POST /api/clips/{id}/references - add reference token with automatic ordinal & position assignment.
    Validates kind constraints and bumps inputs_revision (§6.4).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT mode FROM clips WHERE id = ?", (clip_id,))
        clip_row = cur.fetchone()
        if not clip_row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Clip {clip_id} not found"}})
        mode = clip_row["mode"]

        # Validate mode permissions
        if mode == "T2VA":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "validation", "message": "T2VA does not permit reference tokens."}},
            )
        if mode in {"I2VA", "FL2VA", "L2VA"} and ref_in.kind != "image":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "validation", "message": f"{mode} only permits image frame tokens, not {ref_in.kind}."}},
            )

        # Enforce hard reference budgets (§6.1, PF-20, Criterion A-11)
        if mode == "REF2VA":
            cur.execute("SELECT COUNT(*) FROM references_tokens WHERE clip_id = ?", (clip_id,))
            total_count = cur.fetchone()[0]
            if total_count >= 12:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": "budget_exceeded", "message": "Total reference files limit exceeded (max 12 references)."}},
                )
            if ref_in.kind == "image":
                cur.execute("SELECT COUNT(*) FROM references_tokens WHERE clip_id = ? AND kind = 'image'", (clip_id,))
                if cur.fetchone()[0] >= 9:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"error": {"code": "budget_exceeded", "message": "Image count limit exceeded: clip already has 9 images (max 9)."}},
                    )
            elif ref_in.kind == "video":
                cur.execute("SELECT COUNT(*) FROM references_tokens WHERE clip_id = ? AND kind = 'video'", (clip_id,))
                if cur.fetchone()[0] >= 3:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"error": {"code": "budget_exceeded", "message": "Videos budget exceeded: clip already has 3 videos (max 3)."}},
                    )
            elif ref_in.kind == "audio":
                cur.execute("SELECT COUNT(*) FROM references_tokens WHERE clip_id = ? AND kind = 'audio'", (clip_id,))
                if cur.fetchone()[0] >= 3:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"error": {"code": "budget_exceeded", "message": "Audio budget exceeded: clip already has 3 audio files (max 3)."}},
                    )
            if ref_in.kind in {"video", "audio"}:
                if ref_in.duration_ms is not None and not (2000 <= ref_in.duration_ms <= 15000):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={"error": {"code": "validation", "message": f"Reference duration ({ref_in.duration_ms}ms) must be between 2000 and 15000 ms (2–15s)."}},
                    )

        # Compute next position and ordinal
        cur.execute("SELECT COALESCE(MAX(position), 0) FROM references_tokens WHERE clip_id = ?", (clip_id,))
        next_pos = cur.fetchone()[0] + 1

        cur.execute("SELECT COALESCE(MAX(ordinal), 0) FROM references_tokens WHERE clip_id = ? AND kind = ?", (clip_id, ref_in.kind))
        next_ord = cur.fetchone()[0] + 1

        # Image kind prohibits duration_ms; non-image prohibits width/height
        dur = ref_in.duration_ms if ref_in.kind != "image" else None
        w = ref_in.width_px if ref_in.kind == "image" else None
        h = ref_in.height_px if ref_in.kind == "image" else None

        cur.execute("""
            INSERT INTO references_tokens (
                clip_id, kind, ordinal, caption, role_hint, position, source_file,
                duration_ms, width_px, height_px, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clip_id, ref_in.kind, next_ord, (ref_in.caption or "").strip(), ref_in.role_hint or "",
            next_pos, ref_in.source_file or ref_in.plate_filename or "", dur, w, h, now_iso, now_iso,
        ))
        ref_id = cur.lastrowid

        # Bump clip revision and inputs_revision (marks existing prompts stale per PF-30)
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

        cur.execute("SELECT * FROM references_tokens WHERE id = ?", (ref_id,))
        return dict(cur.fetchone())


@router.put("/clips/{clip_id}/references/{ref_id}")
def update_reference_token(clip_id: int, ref_id: int, updates: ReferenceUpdate) -> dict[str, Any]:
    """PUT /api/clips/{id}/references/{rid} - update reference metadata."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM references_tokens WHERE id = ? AND clip_id = ?", (ref_id, clip_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Reference {ref_id} not found"}})
        curr = dict(row)

        set_clauses = ["updated_at = ?"]
        params = [now_iso]

        if updates.caption is not None:
            set_clauses.append("caption = ?")
            params.append(updates.caption.strip())
        if updates.role_hint is not None:
            set_clauses.append("role_hint = ?")
            params.append(updates.role_hint.strip())
        if updates.source_file is not None:
            set_clauses.append("source_file = ?")
            params.append(updates.source_file.strip())
        if curr["kind"] == "image":
            if updates.width_px is not None:
                set_clauses.append("width_px = ?")
                params.append(updates.width_px)
            if updates.height_px is not None:
                set_clauses.append("height_px = ?")
                params.append(updates.height_px)
        elif curr["kind"] in {"video", "audio"}:
            if updates.duration_ms is not None:
                set_clauses.append("duration_ms = ?")
                params.append(updates.duration_ms)

        params.append(ref_id)
        cur.execute(f"UPDATE references_tokens SET {', '.join(set_clauses)} WHERE id = ?", params)
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

        cur.execute("SELECT * FROM references_tokens WHERE id = ?", (ref_id,))
        return dict(cur.fetchone())


@router.delete("/clips/{clip_id}/references/{ref_id}")
def delete_reference_token(clip_id: int, ref_id: int) -> dict[str, Any]:
    """
    DELETE /api/clips/{id}/references/{rid} - remove reference token.
    Re-sequences remaining positions and ordinals sequentially (§6.4).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT id FROM references_tokens WHERE id = ? AND clip_id = ?", (ref_id, clip_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Reference {ref_id} not found"}})

        cur.execute("DELETE FROM references_tokens WHERE id = ?", (ref_id,))
        _resequence_reference_tokens(cur, clip_id)

        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

    return {"status": "deleted", "reference_id": ref_id}


@router.get("/clips/{clip_id}/instruction-preview")
def get_instruction_preview(clip_id: int) -> dict[str, Any]:
    """
    GET /api/clips/{id}/instruction-preview - pre-generation instruction line preview (§4.4.4, Criterion A-06).
    Uses requested_shot_count or 1 for initial preview display.
    """
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT mode, duration_s, requested_shot_count FROM clips WHERE id = ?", (clip_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Clip {clip_id} not found"}})
        
        mode = row["mode"]
        duration_s = row["duration_s"] or 8
        shot_count = row["requested_shot_count"] or (1 if mode == "FL2VA" else 2)

        line = build_instruction_line(mode, shot_count, duration_s)
        return {
            "mode": mode,
            "shot_count": shot_count,
            "duration_s": duration_s,
            "instruction_line": line or "",
        }
