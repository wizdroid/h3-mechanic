"""REF2VA Mode Backend Routes (§4.4.6, §5.6, §6.1, §6.4, §8.3–§8.6).

Provides:
- Subjects CRUD & re-sequencing (+1000000 offset):
  * GET/POST /api/clips/{id}/subjects
  * PUT/DELETE /api/subjects/{id}
  * POST /api/clips/{id}/subjects/suggest-role
- Subject-Picture Links CRUD:
  * GET/POST /api/clips/{id}/subject-pictures
  * PUT/DELETE /api/subject-pictures/{id}
- Shots CRUD & re-sequencing:
  * GET/POST /api/clips/{id}/shots
  * PUT/DELETE /api/shots/{id}
- Retention Markers CRUD & Sync:
  * GET /api/clips/{id}/retention
  * POST /api/clips/{id}/retention/sync
  * PUT /api/retention/{id}
- Subject Definitions Preview:
  * GET /api/clips/{id}/subject-defs-preview
"""

from __future__ import annotations
from datetime import datetime, timezone
import json
import logging
import sqlite3
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.storage.db import get_connection
from app.engine.subject_builder import build_subject_definitions
from app.resources.vocab import get_task_types, get_retention_markers

logger = logging.getLogger("h3studio.ref2va_routes")
router = APIRouter(prefix="/api", tags=["ref2va"])


# ==============================================================================
# 1. SUBJECTS CRUD (§6.1, §6.4)
# ==============================================================================

class SubjectCreate(BaseModel):
    role: str = "person"
    role_phrase: str
    pronoun: str = "his"
    outfit_noun: str = "outfit"
    appositive: Optional[str] = ""
    feature_list: Optional[str] = ""
    notes: Optional[str] = ""


class SubjectUpdate(BaseModel):
    role: Optional[str] = None
    role_phrase: Optional[str] = None
    pronoun: Optional[str] = None
    outfit_noun: Optional[str] = None
    appositive: Optional[str] = None
    feature_list: Optional[str] = None
    notes: Optional[str] = None


def _resequence_subjects(cur: sqlite3.Cursor, clip_id: int) -> None:
    """Re-sequence subject ordinals 1..N using temporary +1000000 offset (§6.4)."""
    cur.execute("UPDATE subjects SET ordinal = ordinal + 1000000 WHERE clip_id = ?", (clip_id,))
    cur.execute("SELECT id FROM subjects WHERE clip_id = ? ORDER BY ordinal ASC, id ASC", (clip_id,))
    rows = cur.fetchall()
    for new_ord, r in enumerate(rows, start=1):
        cur.execute("UPDATE subjects SET ordinal = ? WHERE id = ?", (new_ord, r["id"]))


@router.get("/clips/{clip_id}/subjects")
def list_subjects(clip_id: int) -> list[dict[str, Any]]:
    """GET /api/clips/{id}/subjects - list subjects in ordinal order."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM subjects WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        return [dict(r) for r in cur.fetchall()]


@router.post("/clips/{clip_id}/subjects")
def create_subject(clip_id: int, sub_in: SubjectCreate) -> dict[str, Any]:
    """POST /api/clips/{id}/subjects - create subject with next ordinal."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT mode FROM clips WHERE id = ?", (clip_id,))
        clip = cur.fetchone()
        if not clip:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Clip {clip_id} not found"}})

        cur.execute("SELECT COALESCE(MAX(ordinal), 0) FROM subjects WHERE clip_id = ?", (clip_id,))
        next_ord = cur.fetchone()[0] + 1

        cur.execute("""
            INSERT INTO subjects (
                clip_id, ordinal, role, role_phrase, pronoun, outfit_noun,
                appositive, feature_list, notes, raw_text, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
        """, (
            clip_id, next_ord, sub_in.role.lower(), sub_in.role_phrase.strip(),
            sub_in.pronoun.lower(), sub_in.outfit_noun.strip(),
            (sub_in.appositive or "").strip(), (sub_in.feature_list or "").strip(),
            (sub_in.notes or "").strip(), now_iso, now_iso,
        ))
        sub_id = cur.lastrowid
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

        cur.execute("SELECT * FROM subjects WHERE id = ?", (sub_id,))
        return dict(cur.fetchone())


@router.put("/subjects/{subject_id}")
def update_subject(subject_id: int, updates: SubjectUpdate) -> dict[str, Any]:
    """PUT /api/subjects/{id} - update subject fields."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Subject {subject_id} not found"}})
        clip_id = row["clip_id"]

        set_clauses = ["updated_at = ?"]
        params = [now_iso]

        if updates.role is not None:
            set_clauses.append("role = ?")
            params.append(updates.role.lower())
        if updates.role_phrase is not None:
            set_clauses.append("role_phrase = ?")
            params.append(updates.role_phrase.strip())
        if updates.pronoun is not None:
            set_clauses.append("pronoun = ?")
            params.append(updates.pronoun.lower())
        if updates.outfit_noun is not None:
            set_clauses.append("outfit_noun = ?")
            params.append(updates.outfit_noun.strip())
        if updates.appositive is not None:
            set_clauses.append("appositive = ?")
            params.append(updates.appositive.strip())
        if updates.feature_list is not None:
            set_clauses.append("feature_list = ?")
            params.append(updates.feature_list.strip())
        if updates.notes is not None:
            set_clauses.append("notes = ?")
            params.append(updates.notes.strip())

        params.append(subject_id)
        cur.execute(f"UPDATE subjects SET {', '.join(set_clauses)} WHERE id = ?", params)
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

        cur.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,))
        return dict(cur.fetchone())


@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int) -> dict[str, Any]:
    """DELETE /api/subjects/{id} - remove subject and resequence ordinals 1..N."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT clip_id FROM subjects WHERE id = ?", (subject_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Subject {subject_id} not found"}})
        clip_id = row["clip_id"]

        cur.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        _resequence_subjects(cur, clip_id)
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

    return {"status": "deleted", "subject_id": subject_id}


class SuggestRoleRequest(BaseModel):
    persona_hint: Optional[str] = ""


@router.post("/clips/{clip_id}/subjects/suggest-role")
def suggest_role_phrase(clip_id: int, req: SuggestRoleRequest = SuggestRoleRequest()) -> dict[str, Any]:
    """POST /api/clips/{id}/subjects/suggest-role - AI helper returning <= 4 words noun role phrase (§5.6, §8.3)."""
    hint = req.persona_hint.strip() if req.persona_hint else "investigator"
    cleaned = " ".join(hint.split()[:4]).lower()
    return {"role_phrase": cleaned or "character"}


# ==============================================================================
# 2. SUBJECT-PICTURE LINKS CRUD (S-03 / §6.1, §6.4, §8.3)
# ==============================================================================

class SubjectPictureCreate(BaseModel):
    subject_id: int
    reference_id: int
    reference_role: str = "identity_anchor"
    anchor_shot_id: Optional[int] = None
    defines_text: Optional[str] = "the layout"


class SubjectPictureUpdate(BaseModel):
    reference_role: Optional[str] = None
    anchor_shot_id: Optional[int] = None
    defines_text: Optional[str] = None


@router.get("/clips/{clip_id}/subject-pictures")
def list_subject_pictures(clip_id: int) -> list[dict[str, Any]]:
    """GET /api/clips/{id}/subject-pictures - list all picture links for clip."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT sp.*, s.ordinal as subject_ordinal, rt.ordinal as reference_ordinal, rt.kind as reference_kind
            FROM subject_pictures sp
            JOIN subjects s ON sp.subject_id = s.id
            JOIN references_tokens rt ON sp.reference_id = rt.id
            WHERE s.clip_id = ?
            ORDER BY s.ordinal ASC, sp.id ASC
        """, (clip_id,))
        return [dict(r) for r in cur.fetchall()]


@router.post("/clips/{clip_id}/subject-pictures")
def create_subject_picture(clip_id: int, sp_in: SubjectPictureCreate) -> dict[str, Any]:
    """POST /api/clips/{id}/subject-pictures - link subject to reference picture."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Validate subject belongs to clip
        cur.execute("SELECT id FROM subjects WHERE id = ? AND clip_id = ?", (sp_in.subject_id, clip_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Subject {sp_in.subject_id} not found in clip {clip_id}"}})

        # Validate reference belongs to clip and is image
        cur.execute("SELECT id, kind FROM references_tokens WHERE id = ? AND clip_id = ?", (sp_in.reference_id, clip_id))
        ref = cur.fetchone()
        if not ref:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Reference {sp_in.reference_id} not found in clip {clip_id}"}})
        if ref["kind"] != "image":
            raise HTTPException(status_code=422, detail={"error": {"code": "validation", "message": "Only image references can be linked in subject_pictures."}})

        try:
            cur.execute("""
                INSERT INTO subject_pictures (
                    subject_id, reference_id, reference_role, anchor_shot_id, defines_text
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                sp_in.subject_id, sp_in.reference_id, sp_in.reference_role,
                sp_in.anchor_shot_id, (sp_in.defines_text or "the layout").strip(),
            ))
            sp_id = cur.lastrowid
            cur.execute(
                "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
                (now_iso, clip_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail={"error": {"code": "conflict", "message": "This subject-reference-role link already exists."}})

        cur.execute("SELECT * FROM subject_pictures WHERE id = ?", (sp_id,))
        return dict(cur.fetchone())


@router.put("/subject-pictures/{link_id}")
def update_subject_picture(link_id: int, updates: SubjectPictureUpdate) -> dict[str, Any]:
    """PUT /api/subject-pictures/{id} - update picture link role or anchor."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT sp.*, s.clip_id FROM subject_pictures sp
            JOIN subjects s ON sp.subject_id = s.id
            WHERE sp.id = ?
        """, (link_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Link {link_id} not found"}})
        clip_id = row["clip_id"]

        set_clauses = []
        params = []
        if updates.reference_role is not None:
            set_clauses.append("reference_role = ?")
            params.append(updates.reference_role)
        if updates.anchor_shot_id is not None:
            set_clauses.append("anchor_shot_id = ?")
            params.append(updates.anchor_shot_id)
        if updates.defines_text is not None:
            set_clauses.append("defines_text = ?")
            params.append(updates.defines_text.strip())

        if set_clauses:
            params.append(link_id)
            cur.execute(f"UPDATE subject_pictures SET {', '.join(set_clauses)} WHERE id = ?", params)
            cur.execute(
                "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
                (now_iso, clip_id),
            )
            conn.commit()

        cur.execute("SELECT * FROM subject_pictures WHERE id = ?", (link_id,))
        return dict(cur.fetchone())


@router.delete("/subject-pictures/{link_id}")
def delete_subject_picture(link_id: int) -> dict[str, Any]:
    """DELETE /api/subject-pictures/{id} - remove picture link."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT sp.*, s.clip_id FROM subject_pictures sp
            JOIN subjects s ON sp.subject_id = s.id
            WHERE sp.id = ?
        """, (link_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Link {link_id} not found"}})
        clip_id = row["clip_id"]

        cur.execute("DELETE FROM subject_pictures WHERE id = ?", (link_id,))
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

    return {"status": "deleted", "link_id": link_id}


# ==============================================================================
# 3. SHOTS CRUD (§6.1, §6.4)
# ==============================================================================

class ShotCreate(BaseModel):
    start_ms: int = 0
    end_ms: int = 3000
    size: Optional[str] = "a medium shot"
    angle: Optional[str] = "at eye level"
    camera_move: Optional[str] = "The camera holds a static shot"
    pacing: Optional[str] = "action"
    events: Optional[str] = ""


class ShotUpdate(BaseModel):
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    size: Optional[str] = None
    angle: Optional[str] = None
    camera_move: Optional[str] = None
    pacing: Optional[str] = None
    events: Optional[str] = None


def _resequence_shots(cur: sqlite3.Cursor, clip_id: int) -> None:
    """Re-sequence shot ordinals 1..N using temporary +1000000 offset (§6.4)."""
    cur.execute("UPDATE shots SET ordinal = ordinal + 1000000 WHERE clip_id = ?", (clip_id,))
    cur.execute("SELECT id FROM shots WHERE clip_id = ? ORDER BY ordinal ASC, id ASC", (clip_id,))
    rows = cur.fetchall()
    for new_ord, r in enumerate(rows, start=1):
        cur.execute("UPDATE shots SET ordinal = ? WHERE id = ?", (new_ord, r["id"]))


@router.get("/clips/{clip_id}/shots")
def list_shots(clip_id: int) -> list[dict[str, Any]]:
    """GET /api/clips/{id}/shots - list shots in ordinal order."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM shots WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        return [dict(r) for r in cur.fetchall()]


@router.post("/clips/{clip_id}/shots")
def create_shot(clip_id: int, shot_in: ShotCreate) -> dict[str, Any]:
    """POST /api/clips/{id}/shots - add shot with next ordinal."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT duration_s FROM clips WHERE id = ?", (clip_id,))
        clip = cur.fetchone()
        if not clip:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Clip {clip_id} not found"}})

        cur.execute("SELECT COALESCE(MAX(ordinal), 0), COALESCE(MAX(end_ms), 0) FROM shots WHERE clip_id = ?", (clip_id,))
        max_ord, max_end = cur.fetchone()
        next_ord = max_ord + 1

        start = shot_in.start_ms if next_ord == 1 else (shot_in.start_ms or max_end)
        end = shot_in.end_ms if shot_in.end_ms > start else start + 3000

        cur.execute("""
            INSERT INTO shots (
                clip_id, ordinal, start_ms, end_ms, size, angle,
                camera_move, pacing, events, reference_anchors_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?)
        """, (
            clip_id, next_ord, start, end, shot_in.size or "a medium shot",
            shot_in.angle or "at eye level", shot_in.camera_move or "The camera holds a static shot",
            shot_in.pacing or "action", shot_in.events or "", now_iso, now_iso,
        ))
        shot_id = cur.lastrowid
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

        cur.execute("SELECT * FROM shots WHERE id = ?", (shot_id,))
        return dict(cur.fetchone())


@router.put("/shots/{shot_id}")
def update_shot(shot_id: int, updates: ShotUpdate) -> dict[str, Any]:
    """PUT /api/shots/{id} - update shot attributes."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT clip_id FROM shots WHERE id = ?", (shot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Shot {shot_id} not found"}})
        clip_id = row["clip_id"]

        set_clauses = ["updated_at = ?"]
        params = [now_iso]

        if updates.start_ms is not None:
            set_clauses.append("start_ms = ?")
            params.append(updates.start_ms)
        if updates.end_ms is not None:
            set_clauses.append("end_ms = ?")
            params.append(updates.end_ms)
        if updates.size is not None:
            set_clauses.append("size = ?")
            params.append(updates.size)
        if updates.angle is not None:
            set_clauses.append("angle = ?")
            params.append(updates.angle)
        if updates.camera_move is not None:
            set_clauses.append("camera_move = ?")
            params.append(updates.camera_move)
        if updates.pacing is not None:
            set_clauses.append("pacing = ?")
            params.append(updates.pacing)
        if updates.events is not None:
            set_clauses.append("events = ?")
            params.append(updates.events)

        params.append(shot_id)
        cur.execute(f"UPDATE shots SET {', '.join(set_clauses)} WHERE id = ?", params)
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

        cur.execute("SELECT * FROM shots WHERE id = ?", (shot_id,))
        return dict(cur.fetchone())


@router.delete("/shots/{shot_id}")
def delete_shot(shot_id: int) -> dict[str, Any]:
    """DELETE /api/shots/{id} - remove shot and resequence ordinals 1..N."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT clip_id FROM shots WHERE id = ?", (shot_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Shot {shot_id} not found"}})
        clip_id = row["clip_id"]

        cur.execute("DELETE FROM shots WHERE id = ?", (shot_id,))
        _resequence_shots(cur, clip_id)
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

    return {"status": "deleted", "shot_id": shot_id}


# ==============================================================================
# 4. RETENTION MARKERS CRUD & SYNCHRONIZER (§6.4, §8.6, Appendix A.9)
# ==============================================================================

class RetentionUpdate(BaseModel):
    marker: Optional[str] = None
    reason: Optional[str] = None
    parenthetical: Optional[str] = None


@router.get("/clips/{clip_id}/retention")
def list_retention_entries(clip_id: int) -> list[dict[str, Any]]:
    """GET /api/clips/{id}/retention - list retention entries."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM retention_markers WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        return [dict(r) for r in cur.fetchall()]


@router.post("/clips/{clip_id}/retention/sync")
def sync_retention_entries(clip_id: int) -> list[dict[str, Any]]:
    """
    POST /api/clips/{id}/retention/sync - synchronize retention rows per §6.4, §8.6:
    Creates rows for every subject, every anchor picture, every video, and every audio.
    Preserves existing user markers and non-empty reasons.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM subjects WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        subjects = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM references_tokens WHERE clip_id = ? ORDER BY position ASC", (clip_id,))
        references = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM retention_markers WHERE clip_id = ?", (clip_id,))
        existing_rows = [dict(r) for r in cur.fetchall()]

        # Index existing user rows by subject_id and reference_id
        user_by_subj = {r["subject_id"]: r for r in existing_rows if r["subject_id"]}
        user_by_ref = {r["reference_id"]: r for r in existing_rows if r["reference_id"]}

        # Clear old rows and recreate cleanly
        cur.execute("DELETE FROM retention_markers WHERE clip_id = ?", (clip_id,))

        next_ord = 1

        # 1. Subject entries
        for s in subjects:
            sid = s["id"]
            existing = user_by_subj.get(sid)
            role = (s.get("role") or "person").lower()
            default_marker = "partially_preserved" if role in {"outfit", "prop", "accessory"} else "fully_preserved"
            marker = existing["marker"] if existing else default_marker
            reason = existing["reason"] if existing and existing["reason"] else "Key visual attributes and features are maintained."
            parenthetical = existing["parenthetical"] if existing else "(appears in [Shot 1])"

            cur.execute("""
                INSERT INTO retention_markers (
                    clip_id, ordinal, area, subject_id, reference_id,
                    parenthetical, shot_ordinals_json, marker, reason,
                    marker_source, created_at, updated_at
                ) VALUES (?, ?, 'visual', ?, NULL, ?, '[]', ?, ?, 'default', ?, ?)
            """, (clip_id, next_ord, sid, parenthetical, marker, reason, now_iso, now_iso))
            next_ord += 1

        # 2. Reference entries (Picture Anchors, Videos, Audios)
        # Fetch anchor roles from subject_pictures
        cur.execute("""
            SELECT sp.*, rt.ordinal as reference_ordinal
            FROM subject_pictures sp
            JOIN references_tokens rt ON sp.reference_id = rt.id
            WHERE rt.clip_id = ? AND sp.reference_role IN ('first_frame', 'keyframe', 'last_frame', 'composition_anchor', 'framing_reference')
        """, (clip_id,))
        anchor_rows = [dict(r) for r in cur.fetchall()]
        anchor_role_display = {
            "first_frame": "first frame",
            "keyframe": "keyframe",
            "last_frame": "last frame",
            "composition_anchor": "composition anchor",
            "framing_reference": "framing reference",
        }
        for anchor in anchor_rows:
            rid = anchor["reference_id"]
            existing = user_by_ref.get(rid)
            role_name = anchor_role_display.get(anchor["reference_role"], anchor["reference_role"])
            shot_ord = anchor.get("anchor_shot_ordinal") or 1
            parenthetical = f"[Shot {shot_ord}] {role_name}"
            marker = existing["marker"] if existing else "fully_preserved"
            reason = existing["reason"] if existing and existing["reason"] else "Defines camera framing and visual anchor position."
            cur.execute("""
                INSERT INTO retention_markers (
                    clip_id, ordinal, area, subject_id, reference_id,
                    parenthetical, shot_ordinals_json, marker, reason,
                    marker_source, created_at, updated_at
                ) VALUES (?, ?, 'visual', NULL, ?, ?, '[]', ?, ?, 'default', ?, ?)
            """, (clip_id, next_ord, rid, parenthetical, marker, reason, now_iso, now_iso))
            next_ord += 1

        for r in references:
            rid = r["id"]
            kind = r["kind"]
            existing = user_by_ref.get(rid)

            if kind == "video":
                marker = existing["marker"] if existing else "weak_reference"
                reason = existing["reason"] if existing and existing["reason"] else "Cut pacing and timing structure inform sequence flow."
                parenthetical = existing["parenthetical"] if existing else "cut and pacing structure"
                cur.execute("""
                    INSERT INTO retention_markers (
                        clip_id, ordinal, area, subject_id, reference_id,
                        parenthetical, shot_ordinals_json, marker, reason,
                        marker_source, created_at, updated_at
                    ) VALUES (?, ?, 'visual', NULL, ?, ?, '[]', ?, ?, 'default', ?, ?)
                """, (clip_id, next_ord, rid, parenthetical, marker, reason, now_iso, now_iso))
                next_ord += 1
            elif kind == "audio":
                marker = existing["marker"] if existing else "reference"
                reason = existing["reason"] if existing and existing["reason"] else "Acoustic delivery and timbre match dialogue lines."
                cur.execute("""
                    INSERT INTO retention_markers (
                        clip_id, ordinal, area, subject_id, reference_id,
                        parenthetical, shot_ordinals_json, marker, reason,
                        marker_source, created_at, updated_at
                    ) VALUES (?, ?, 'audio', NULL, ?, '', '[]', ?, ?, 'default', ?, ?)
                """, (clip_id, next_ord, rid, marker, reason, now_iso, now_iso))
                next_ord += 1

        conn.commit()

        cur.execute("SELECT * FROM retention_markers WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        return [dict(r) for r in cur.fetchall()]


@router.put("/retention/{entry_id}")
def update_retention_entry(entry_id: int, updates: RetentionUpdate) -> dict[str, Any]:
    """PUT /api/retention/{id} - update retention entry marker or reason."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM retention_markers WHERE id = ?", (entry_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Retention entry {entry_id} not found"}})
        clip_id = row["clip_id"]

        set_clauses = ["updated_at = ?"]
        params = [now_iso]

        if updates.marker is not None:
            set_clauses.append("marker = ?")
            set_clauses.append("marker_source = 'user'")
            params.append(updates.marker.strip())
        if updates.reason is not None:
            set_clauses.append("reason = ?")
            params.append(updates.reason.strip())
        if updates.parenthetical is not None:
            set_clauses.append("parenthetical = ?")
            params.append(updates.parenthetical.strip())

        params.append(entry_id)
        cur.execute(f"UPDATE retention_markers SET {', '.join(set_clauses)} WHERE id = ?", params)
        cur.execute(
            "UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?",
            (now_iso, clip_id),
        )
        conn.commit()

        cur.execute("SELECT * FROM retention_markers WHERE id = ?", (entry_id,))
        return dict(cur.fetchone())


# ==============================================================================
# 5. SUBJECT DEFINITIONS PREVIEW (§8.3, Appendix A.9)
# ==============================================================================

@router.get("/clips/{clip_id}/subject-defs-preview")
def get_subject_definitions_preview(clip_id: int) -> dict[str, Any]:
    """GET /api/clips/{id}/subject-defs-preview - deterministic compiled subject_definitions."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM subjects WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        subjects = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT sp.*, rt.ordinal as reference_ordinal, rt.kind as reference_kind, COALESCE(sh.ordinal, 1) as anchor_shot_ordinal
            FROM subject_pictures sp
            JOIN subjects s ON sp.subject_id = s.id
            JOIN references_tokens rt ON sp.reference_id = rt.id
            LEFT JOIN shots sh ON sp.anchor_shot_id = sh.id
            WHERE s.clip_id = ?
        """, (clip_id,))
        subject_pictures = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM references_tokens WHERE clip_id = ? ORDER BY position ASC", (clip_id,))
        references = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM speakers WHERE clip_id = ?", (clip_id,))
        speakers = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM dialogue_lines WHERE clip_id = ? ORDER BY line_order ASC", (clip_id,))
        lines = [dict(r) for r in cur.fetchall()]

        from app.validation.estimators import assign_speaker_numbers
        speaker_id_to_num = assign_speaker_numbers(lines)

        defs_text = build_subject_definitions(
            subjects=subjects,
            subject_pictures=subject_pictures,
            references=references,
            speakers=speakers,
            speaker_id_to_num=speaker_id_to_num,
        )

        return {
            "clip_id": clip_id,
            "subject_count": len(subjects),
            "subject_definitions": defs_text,
        }


# ==============================================================================
# 6. TASK TYPES UPDATE (§6.4, §8.5, Appendix A.9)
# ==============================================================================

class TaskTypesUpdate(BaseModel):
    task_types: list[str]


@router.put("/clips/{clip_id}/task-types")
def update_clip_task_types(clip_id: int, payload: TaskTypesUpdate) -> dict[str, Any]:
    """PUT /api/clips/{id}/task-types - update user-selected task types and touch flag."""
    order = [
        "reference generation",
        "keyframe completion",
        "video editing",
        "video continuation",
        "audio reuse",
        "audio reference",
    ]
    seen = set()
    cleaned = []
    for t in order:
        if t in payload.task_types and t not in seen:
            cleaned.append(t)
            seen.add(t)
    if not cleaned:
        cleaned = ["reference generation"]

    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id FROM clips WHERE id = ?", (clip_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Clip {clip_id} not found"}})

        cur.execute("""
            UPDATE clips
            SET task_types_json = ?, task_types_touched = 1, inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ?
            WHERE id = ?
        """, (json.dumps(cleaned), now_iso, clip_id))
        conn.commit()

    return {"status": "ok", "task_types": cleaned}

