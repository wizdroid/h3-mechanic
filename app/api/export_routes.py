"""Export API routes and clipboard helpers (§10.1, §10.2)."""

from __future__ import annotations
import sqlite3
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import EXPORTS_DIR
from app.storage.db import get_connection
from app.engine.exporter import (
    export_clip,
    suggest_next_clip_number,
    check_collision,
    build_plates_content,
    ExportCollisionError,
    PreflightBlockedError,
)

router = APIRouter(prefix="/api", tags=["export"])

class ExportRequest(BaseModel):
    clip_number: Optional[int] = None
    overwrite: bool = False

@router.get("/clips/{clip_id}/export-preview")
def get_export_preview(clip_id: int):
    """Preview export filenames, suggested NN, prompt content, and collision warnings."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        clip = cur.fetchone()
        if not clip:
            raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")

        cur.execute("SELECT * FROM prompts WHERE clip_id = ? ORDER BY id DESC LIMIT 1", (clip_id,))
        prompt = cur.fetchone()
        if not prompt:
            raise HTTPException(status_code=404, detail="No prompt found for this clip")

        suggested_nn = suggest_next_clip_number()
        duration_s = clip["duration_s"]
        mode = clip["mode"]

        prompt_fname = f"clip-{suggested_nn:02d}-{duration_s}s.txt"
        plates_fname = f"clip-{suggested_nn:02d}-PLATES.txt" if mode == "REF2VA" else None

        plates_content = None
        if mode == "REF2VA":
            cur.execute("SELECT * FROM references_tokens WHERE clip_id = ? ORDER BY position ASC", (clip_id,))
            refs = [dict(r) for r in cur.fetchall()]
            cur.execute("""
                SELECT sp.* FROM subject_pictures sp
                JOIN subjects s ON sp.subject_id = s.id
                WHERE s.clip_id = ?
            """, (clip_id,))
            sub_pics = [dict(r) for r in cur.fetchall()]
            plates_content = build_plates_content(refs, sub_pics)

        colliding = check_collision(suggested_nn)

        return {
            "clip_id": clip_id,
            "suggested_clip_number": suggested_nn,
            "prompt_filename": prompt_fname,
            "plates_filename": plates_fname,
            "prompt_body": prompt["body"],
            "plates_content": plates_content,
            "colliding_files": colliding,
        }

@router.post("/clips/{clip_id}/export")
def perform_export(clip_id: int, req: ExportRequest = ExportRequest()):
    """
    Execute full atomic clip export (§10.1):
    Runs preflight, validates collision on integer NN, creates backup snapshot, writes files.
    """
    nn = req.clip_number if req.clip_number is not None else suggest_next_clip_number()

    try:
        result = export_clip(clip_id=clip_id, clip_number=nn, overwrite=req.overwrite)
        return result
    except ExportCollisionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "collision",
                    "message": f"Clip number {e.clip_number} collides with existing files: {e.colliding_files}",
                    "clip_number": e.clip_number,
                    "colliding_files": e.colliding_files,
                }
            },
        )
    except PreflightBlockedError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "preflight_blocked",
                    "message": str(e),
                    "violations": [v.to_dict() for v in e.violations],
                }
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
