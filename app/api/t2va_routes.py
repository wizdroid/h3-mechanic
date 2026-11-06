"""T2VA and Shared Generator Web Shell API Routes (§4.1–§4.4, §5.6).

Provides:
- GET /api/modes: Mode registry metadata (T2VA, I2VA, FL2VA, L2VA, REF2VA)
- GET /api/voices: Voice library vocabulary
- GET/PUT /api/settings: System and generator configuration
- GET/POST /api/projects: List and create projects
- GET/POST /api/projects/{id}/clips: List and create clips
- GET/PUT /api/clips/{id}: Read and autosave clip metadata with revision check (§5.7)
- GET/POST /api/clips/{id}/lines: List and create dialogue lines
- PUT/DELETE /api/lines/{line_id}: Update and delete dialogue lines
- GET/POST /api/clips/{id}/speakers: List and create speakers
- PUT/DELETE /api/speakers/{speaker_id}: Update and delete speakers
"""

from __future__ import annotations
from datetime import datetime, timezone
import json
import logging
import sqlite3
from typing import Any, Optional
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.storage.db import get_connection
from app.resources.vocab import get_voices, get_styles, get_scripts

logger = logging.getLogger("h3studio.t2va_routes")
router = APIRouter(prefix="/api", tags=["t2va_and_shell"])

# ==============================================================================
# 1. MODES REGISTRY (§5.6)
# ==============================================================================

MODES_REGISTRY = [
    {
        "id": "T2VA",
        "label": "T2VA",
        "alias": "Text-to-Video-Audio",
        "ratio_policy": "concrete",
        "default_ratio": "16:9",
        "allowed_ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
        "description": "Generate multi-shot prompt purely from text seed, style, and optional dialogue lines.",
    },
    {
        "id": "I2VA",
        "label": "I2VA",
        "alias": "Image-to-Video-Audio",
        "ratio_policy": "adaptive",
        "default_ratio": "adaptive",
        "allowed_ratios": ["adaptive"],
        "description": "Single initial frame reference (<Picture 1>) anchoring the opening of Shot 1.",
    },
    {
        "id": "FL2VA",
        "label": "FL2VA (flf2va)",
        "alias": "First-Last-Frame-to-Video-Audio",
        "ratio_policy": "adaptive",
        "default_ratio": "adaptive",
        "allowed_ratios": ["adaptive"],
        "description": "First frame (<Picture 1>) and last frame (<Picture 2>) transition sequence.",
    },
    {
        "id": "L2VA",
        "label": "L2VA (lf2va)",
        "alias": "Last-Frame-to-Video-Audio",
        "ratio_policy": "adaptive",
        "default_ratio": "adaptive",
        "allowed_ratios": ["adaptive"],
        "description": "Sequence leading up to and concluding on the target final frame (<Picture 1>).",
    },
    {
        "id": "REF2VA",
        "label": "REF2VA",
        "alias": "Reference-to-Video-Audio",
        "ratio_policy": "both",
        "default_ratio": "adaptive",
        "allowed_ratios": ["adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
        "description": "Multi-modal reference composition using pictures, audio timbre references, and video anchors.",
    },
]

@router.get("/modes")
def list_modes() -> list[dict[str, Any]]:
    """GET /api/modes - registry metadata for UI sub-tabs."""
    return MODES_REGISTRY

@router.get("/voices")
def list_voices() -> dict[str, Any]:
    """GET /api/voices - voice library vocabulary."""
    return get_voices()

# ==============================================================================
# 2. SETTINGS (§4.4.7, §7.5)
# ==============================================================================

DEFAULT_SETTINGS: dict[str, str] = {
    "ollama_endpoint": "http://127.0.0.1:11434",
    "drafter_model": "qwen2.5:7b-instruct",
    "temperature": "0.2",
    "num_ctx": "8192",
    "timeout_s": "120",
    "keep_alive": "10m",
    "seed_mode": "auto",
    "seed_value": "0",
    "max_fixer_retries": "2",
    "h3_model": "MiniMax-H3",
    "default_duration_s": "8",
    "default_resolution": "768P",
    "default_ratio": "16:9",
    "default_style_id": "plain",
    "default_plain_style_pair": "Live-action, cinematic",
    "default_language": "English",
    "default_audio_policy": "dialogue_only",
    "export_directory": "/home/wizdroid/Applications/h3-mechanic/data/exports",
    "listen_port": "9013",
    "collision_policy": "auto_increment",
    "theme": "nord-dark",
}

@router.get("/settings")
def get_settings() -> dict[str, str]:
    """GET /api/settings - retrieve merged global settings."""
    merged = dict(DEFAULT_SETTINGS)
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings")
        for row in cur.fetchall():
            merged[row["key"]] = row["value"]
    return merged

@router.put("/settings")
def update_settings(updates: dict[str, Any]) -> dict[str, str]:
    """PUT /api/settings - update settings in database."""
    with get_connection() as conn:
        cur = conn.cursor()
        for k, v in updates.items():
            cur.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(k), str(v)),
            )
        conn.commit()
    return get_settings()

# ==============================================================================
# 3. PROJECTS CRUD (§5.6)
# ==============================================================================

class ProjectCreate(BaseModel):
    name: str
    notes: Optional[str] = ""

@router.get("/projects")
def list_projects() -> list[dict[str, Any]]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM projects ORDER BY id DESC")
        return [dict(r) for r in cur.fetchall()]

@router.post("/projects")
def create_project(data: ProjectCreate) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (data.name.strip(), data.notes or "", now_iso, now_iso),
            )
            proj_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "validation", "message": f"Project '{data.name}' already exists."}},
            )
    return {"id": proj_id, "name": data.name, "notes": data.notes, "created_at": now_iso, "updated_at": now_iso}

# ==============================================================================
# 4. CLIPS CRUD (§4.4.1, §5.6, §6.4)
# ==============================================================================

class ClipCreate(BaseModel):
    name: Optional[str] = "Clip"
    mode: Optional[str] = "T2VA"
    h3_model: Optional[str] = "MiniMax-H3"
    duration_s: Optional[int] = 8
    resolution: Optional[str] = "768P"
    ratio: Optional[str] = "16:9"
    style_id: Optional[str] = "plain"
    plain_style_pair: Optional[str] = "Live-action, cinematic"
    language: Optional[str] = "English"
    audio_policy: Optional[str] = "dialogue_only"
    seed_text: Optional[str] = ""
    action_text: Optional[str] = ""
    requested_shot_count: Optional[int] = None

@router.get("/projects/{project_id}/clips")
def list_project_clips(project_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM clips WHERE project_id = ? ORDER BY id DESC", (project_id,))
        return [dict(r) for r in cur.fetchall()]

@router.post("/projects/{project_id}/clips")
def create_clip(project_id: int, clip_in: ClipCreate) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Project {project_id} not found"}})

        # Auto-name clip if default
        name = clip_in.name
        if name == "Clip":
            cur.execute("SELECT COUNT(*) FROM clips WHERE project_id = ?", (project_id,))
            cnt = cur.fetchone()[0] + 1
            name = f"Clip-{cnt:02d}"

        # Validate mode ratio policy (§4.4.1, PF-11)
        concrete_ratios = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}
        if clip_in.mode == "T2VA" and clip_in.ratio not in concrete_ratios:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "validation", "message": f"T2VA requires concrete ratio ({sorted(concrete_ratios)}); cannot be '{clip_in.ratio}'."}}
            )
        if clip_in.mode in {"I2VA", "FL2VA", "L2VA"} and clip_in.ratio != "adaptive":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "validation", "message": f"{clip_in.mode} ratio is locked to 'adaptive'; cannot be '{clip_in.ratio}'."}}
            )

        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                style_id, plain_style_pair, language, audio_policy, seed_text,
                action_text, custom_soundscape, custom_music, task_types_json,
                requested_shot_count, manual_draft, manual_template,
                revision, inputs_revision, status, created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, '', '', '[]',
                ?, 0, '',
                1, 1, 'draft', ?, ?
            )
        """, (
            project_id, name, clip_in.mode, clip_in.h3_model, clip_in.duration_s,
            clip_in.resolution, clip_in.ratio, clip_in.style_id, clip_in.plain_style_pair,
            clip_in.language, clip_in.audio_policy, clip_in.seed_text or "",
            clip_in.action_text or "", clip_in.requested_shot_count,
            now_iso, now_iso,
        ))
        clip_id = cur.lastrowid
        conn.commit()

        cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        return dict(cur.fetchone())

@router.get("/clips/{clip_id}")
def get_clip(clip_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Clip {clip_id} not found"}})
        clip = dict(row)

        # Attach latest prompt if selected
        selected_pid = clip.get("selected_prompt_id")
        if selected_pid:
            cur.execute("SELECT * FROM prompts WHERE id = ?", (selected_pid,))
            p_row = cur.fetchone()
            clip["selected_prompt"] = dict(p_row) if p_row else None
        else:
            cur.execute("SELECT * FROM prompts WHERE clip_id = ? ORDER BY id DESC LIMIT 1", (clip_id,))
            p_row = cur.fetchone()
            clip["selected_prompt"] = dict(p_row) if p_row else None

        # Fetch lines count
        cur.execute("SELECT COUNT(*) FROM dialogue_lines WHERE clip_id = ?", (clip_id,))
        clip["dialogue_count"] = cur.fetchone()[0]

        return clip

@router.put("/clips/{clip_id}")
def update_clip(
    clip_id: int,
    updates: dict[str, Any],
    if_match: Optional[str] = Header(None, alias="If-Match"),
) -> dict[str, Any]:
    """
    PUT /api/clips/{id} - Debounced clip update with optimistic locking (§5.7).
    Requires If-Match: <revision> if supplied.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Clip {clip_id} not found"}})
        curr = dict(row)

        if if_match is not None:
            try:
                expected_rev = int(if_match.strip().strip('"'))
                if expected_rev != curr["revision"]:
                    raise HTTPException(
                        status_code=status.HTTP_412_PRECONDITION_FAILED,
                        detail={
                            "error": {
                                "code": "precondition",
                                "message": f"Clip revision conflict: current {curr['revision']} != expected {expected_rev}",
                                "current_revision": curr["revision"],
                            }
                        },
                    )
            except ValueError:
                pass

        # Validate mode ratio policy (§4.4.1, PF-11)
        target_mode = updates.get("mode", curr["mode"])
        target_ratio = updates.get("ratio", curr["ratio"])
        concrete_ratios = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}
        if target_mode == "T2VA" and target_ratio not in concrete_ratios:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "validation", "message": f"T2VA requires concrete ratio ({sorted(concrete_ratios)}); cannot be '{target_ratio}'."}}
            )
        if target_mode in {"I2VA", "FL2VA", "L2VA"} and target_ratio != "adaptive":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "validation", "message": f"{target_mode} ratio is locked to 'adaptive'; cannot be '{target_ratio}'."}}
            )

        # Check which columns trigger inputs_revision increment (§6.4)
        inputs_columns = {
            "mode", "h3_model", "style_id", "plain_style_pair", "duration_s",
            "resolution", "ratio", "language", "audio_policy", "seed_text",
            "action_text", "custom_soundscape", "custom_music", "task_types_json",
            "requested_shot_count", "manual_draft", "manual_template"
        }

        inputs_changed = any(k in inputs_columns and updates.get(k) != curr.get(k) for k in updates)
        new_rev = curr["revision"] + 1
        new_inputs_rev = curr["inputs_revision"] + (1 if inputs_changed else 0)

        # Status transition: if inputs changed and status was not draft, reset to draft (§6.5)
        new_status = curr["status"]
        if inputs_changed and curr["status"] in {"preflight", "fixed", "blocked", "exported"}:
            new_status = "draft"

        # Filter permitted keys
        allowed_keys = {
            "name", "mode", "h3_model", "duration_s", "resolution", "ratio",
            "style_id", "plain_style_pair", "language", "audio_policy",
            "seed_text", "action_text", "custom_soundscape", "custom_music",
            "task_types_json", "requested_shot_count", "manual_draft",
            "manual_template", "status", "selected_prompt_id"
        }

        set_clauses = ["revision = ?", "inputs_revision = ?", "updated_at = ?"]
        params = [new_rev, new_inputs_rev, now_iso]

        if inputs_changed:
            set_clauses.append("status = ?")
            params.append(new_status)

        for k, v in updates.items():
            if k in allowed_keys and k != "status":
                set_clauses.append(f"{k} = ?")
                params.append(v)

        params.append(clip_id)
        cur.execute(f"UPDATE clips SET {', '.join(set_clauses)} WHERE id = ?", params)
        conn.commit()

        cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        return dict(cur.fetchone())

# ==============================================================================
# 5. DIALOGUE LINES CRUD (§4.4.2, §5.6)
# ==============================================================================

class LineCreate(BaseModel):
    speaker_id: Optional[int] = None
    speaker_id_2: Optional[int] = None
    language: Optional[str] = "English"
    text_raw: str
    gloss: Optional[str] = ""
    delivery: Optional[str] = "none"
    voice_source: Optional[str] = ""
    accent: Optional[str] = ""
    is_voiceover: Optional[int] = 0
    voiceover: Optional[int] = None
    cutoff: Optional[int] = 0
    crosses_cut: Optional[int] = 0
    dest_shot_id: Optional[int] = None
    line_order: Optional[int] = 1

@router.get("/clips/{clip_id}/lines")
def list_dialogue_lines(clip_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM dialogue_lines WHERE clip_id = ? ORDER BY line_order ASC, id ASC", (clip_id,))
        return [dict(r) for r in cur.fetchall()]

@router.post("/clips/{clip_id}/lines")
def create_dialogue_line(clip_id: int, line_in: LineCreate) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # If line_order not specified or default 1, compute max + 1
        cur.execute("SELECT COALESCE(MAX(line_order), 0) FROM dialogue_lines WHERE clip_id = ?", (clip_id,))
        next_order = cur.fetchone()[0] + 1
        order = line_in.line_order if line_in.line_order > 1 else next_order

        # Ensure a speaker exists if not provided
        spk_id = line_in.speaker_id
        if not spk_id:
            cur.execute("SELECT id FROM speakers WHERE clip_id = ? LIMIT 1", (clip_id,))
            row = cur.fetchone()
            if row:
                spk_id = row["id"]
            else:
                cur.execute(
                    "INSERT INTO speakers (clip_id, display_name, persona, voice_source, accent, pronoun, created_at, updated_at) VALUES (?, 'Speaker 1', 'the character', 'F1', '', 'his', ?, ?)",
                    (clip_id, now_iso, now_iso),
                )
                spk_id = cur.lastrowid

        vo_val = line_in.is_voiceover if line_in.voiceover is None else line_in.voiceover
        cur.execute("""
            INSERT INTO dialogue_lines (
                clip_id, line_order, speaker_id, speaker_id_2, language,
                text_raw, gloss, delivery, voice_source, accent,
                is_voiceover, cutoff, crosses_cut, dest_shot_id,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clip_id, order, spk_id, line_in.speaker_id_2, line_in.language,
            line_in.text_raw, line_in.gloss or "", line_in.delivery or "none",
            line_in.voice_source or "", line_in.accent or "",
            vo_val or 0, line_in.cutoff or 0,
            line_in.crosses_cut or 0, line_in.dest_shot_id,
            now_iso, now_iso,
        ))
        line_id = cur.lastrowid

        # Bump clip inputs_revision
        cur.execute("UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?", (now_iso, clip_id))
        conn.commit()

        cur.execute("SELECT * FROM dialogue_lines WHERE id = ?", (line_id,))
        return dict(cur.fetchone())

@router.put("/lines/{line_id}")
def update_dialogue_line(line_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM dialogue_lines WHERE id = ?", (line_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Line {line_id} not found"}})
        curr = dict(row)
        clip_id = curr["clip_id"]

        allowed_keys = {
            "speaker_id", "speaker_id_2", "language", "text_raw", "gloss",
            "delivery", "voice_source", "accent", "is_voiceover", "cutoff",
            "crosses_cut", "dest_shot_id", "line_order"
        }
        set_clauses = ["updated_at = ?"]
        params = [now_iso]

        if "voiceover" in updates and "is_voiceover" not in updates:
            updates["is_voiceover"] = updates["voiceover"]

        for k, v in updates.items():
            if k in allowed_keys:
                set_clauses.append(f"{k} = ?")
                params.append(v)

        params.append(line_id)
        cur.execute(f"UPDATE dialogue_lines SET {', '.join(set_clauses)} WHERE id = ?", params)
        cur.execute("UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?", (now_iso, clip_id))
        conn.commit()

        cur.execute("SELECT * FROM dialogue_lines WHERE id = ?", (line_id,))
        return dict(cur.fetchone())

@router.delete("/lines/{line_id}")
def delete_dialogue_line(line_id: int) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT clip_id FROM dialogue_lines WHERE id = ?", (line_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Line {line_id} not found"}})
        clip_id = row[0]

        cur.execute("DELETE FROM dialogue_lines WHERE id = ?", (line_id,))
        cur.execute("UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?", (now_iso, clip_id))
        conn.commit()
    return {"status": "deleted", "line_id": line_id}

# ==============================================================================
# 6. SPEAKERS CRUD (§4.4.1, §5.6)
# ==============================================================================

class SpeakerCreate(BaseModel):
    display_name: str
    persona: Optional[str] = "the character"
    voice_source: Optional[str] = "F1"
    accent: Optional[str] = ""
    pronoun: Optional[str] = "his"
    subject_id: Optional[int] = None
    audio_reference_id: Optional[int] = None

@router.get("/clips/{clip_id}/speakers")
def list_speakers(clip_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM speakers WHERE clip_id = ? ORDER BY id ASC", (clip_id,))
        return [dict(r) for r in cur.fetchall()]

@router.post("/clips/{clip_id}/speakers")
def create_speaker(clip_id: int, spk: SpeakerCreate) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO speakers (clip_id, display_name, persona, voice_source, accent, pronoun, subject_id, audio_reference_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clip_id, spk.display_name.strip(), spk.persona.strip(), spk.voice_source or "F1",
            spk.accent or "", spk.pronoun or "his", spk.subject_id, spk.audio_reference_id, now_iso, now_iso
        ))
        spk_id = cur.lastrowid
        cur.execute("UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?", (now_iso, clip_id))
        conn.commit()

        cur.execute("SELECT * FROM speakers WHERE id = ?", (spk_id,))
        return dict(cur.fetchone())

@router.put("/speakers/{speaker_id}")
def update_speaker(speaker_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT clip_id FROM speakers WHERE id = ?", (speaker_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Speaker {speaker_id} not found"}})
        clip_id = row["clip_id"]

        allowed_keys = {"display_name", "persona", "voice_source", "accent", "pronoun", "audio_reference_id", "subject_id"}
        set_clauses = ["updated_at = ?"]
        params = [now_iso]

        for k, v in updates.items():
            if k in allowed_keys:
                set_clauses.append(f"{k} = ?")
                params.append(v)

        params.append(speaker_id)
        cur.execute(f"UPDATE speakers SET {', '.join(set_clauses)} WHERE id = ?", params)
        cur.execute("UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?", (now_iso, clip_id))
        conn.commit()

        cur.execute("SELECT * FROM speakers WHERE id = ?", (speaker_id,))
        return dict(cur.fetchone())

@router.delete("/speakers/{speaker_id}")
def delete_speaker(speaker_id: int) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT clip_id FROM speakers WHERE id = ?", (speaker_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": f"Speaker {speaker_id} not found"}})
        clip_id = row[0]

        cur.execute("DELETE FROM speakers WHERE id = ?", (speaker_id,))
        cur.execute("UPDATE clips SET inputs_revision = inputs_revision + 1, revision = revision + 1, updated_at = ? WHERE id = ?", (now_iso, clip_id))
        conn.commit()
    return {"status": "deleted", "speaker_id": speaker_id}
