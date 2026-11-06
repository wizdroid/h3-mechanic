"""Validation endpoints and preflight routes for H3 Prompt Studio (§1.5, §9.4)."""

from __future__ import annotations
import json
import sqlite3
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field

from app.storage.db import get_connection
from app.validation.parser import parse_prompt, ParsedPrompt
from app.validation.registry import default_registry, ValidationContext, Violation
from app.validation.autofix import run_deterministic_autofix
from app.resources.vocab import (
    load_resource,
    get_camera_moves,
    get_mood_words,
    get_sound_lexicon,
    get_scripts,
    get_styles,
    get_voices,
    get_deliveries,
    get_shot_budgets,
    get_task_types,
    get_retention_markers,
    get_accents,
)

router = APIRouter(prefix="/api", tags=["validation"])

ALLOWED_OVERRIDE_RULES = {"PF-04", "PF-05", "PF-10", "PF-34"}

class OverrideRequest(BaseModel):
    rule_id: str
    note: str

class PreflightRequest(BaseModel):
    body: Optional[str] = None
    run_autofix: bool = False

def _fetch_clip_context(conn: sqlite3.Connection, clip_id: int, prompt_body: Optional[str] = None) -> ValidationContext:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
    clip_row = cur.fetchone()
    if not clip_row:
        raise HTTPException(status_code=404, detail=f"Clip {clip_id} not found")
    clip = dict(clip_row)
    if "video_model" not in clip and "h3_model" in clip:
        clip["video_model"] = clip["h3_model"]
    if "style" not in clip and "style_id" in clip:
        clip["style"] = clip["style_id"]

    # Fetch latest prompt if not provided
    cur.execute("SELECT * FROM prompts WHERE clip_id = ? ORDER BY id DESC LIMIT 1", (clip_id,))
    prompt_row = cur.fetchone()
    prompt = dict(prompt_row) if prompt_row else None

    # Overrides from prompt
    overrides = {}
    if prompt and prompt.get("overrides_json"):
        try:
            raw_ovr = json.loads(prompt["overrides_json"])
            if isinstance(raw_ovr, dict):
                overrides = raw_ovr
            elif isinstance(raw_ovr, list):
                for item in raw_ovr:
                    if isinstance(item, dict) and "rule_id" in item:
                        overrides[item["rule_id"]] = item
        except Exception:
            overrides = {}

    # References
    cur.execute("SELECT * FROM references_tokens WHERE clip_id = ? ORDER BY position ASC", (clip_id,))
    references = [dict(r) for r in cur.fetchall()]

    # Subjects
    cur.execute("SELECT * FROM subjects WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
    subjects = [dict(r) for r in cur.fetchall()]

    # Subject Pictures
    cur.execute("""
        SELECT sp.* FROM subject_pictures sp
        JOIN subjects s ON sp.subject_id = s.id
        WHERE s.clip_id = ?
    """, (clip_id,))
    subject_pictures = [dict(r) for r in cur.fetchall()]

    # Shots
    cur.execute("SELECT * FROM shots WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
    shots = [dict(r) for r in cur.fetchall()]

    # Speakers
    cur.execute("SELECT * FROM speakers WHERE clip_id = ?", (clip_id,))
    speakers = [dict(r) for r in cur.fetchall()]

    # Dialogue Lines
    cur.execute("SELECT * FROM dialogue_lines WHERE clip_id = ? ORDER BY line_order ASC", (clip_id,))
    lines = [dict(r) for r in cur.fetchall()]

    body = prompt_body or (prompt.get("body") if prompt else "")
    parsed_prompt = parse_prompt(body)

    return ValidationContext(
        clip=clip,
        parsed_prompt=parsed_prompt,
        prompt=prompt,
        lines=lines,
        speakers=speakers,
        subjects=subjects,
        subject_pictures=subject_pictures,
        references=references,
        shots=shots,
        overrides=overrides,
    )

@router.post("/clips/{clip_id}/validate-inputs")
def validate_inputs(clip_id: int):
    """
    Stage 0 input validation (§3, §9):
    Runs PF-11, PF-13, PF-20, PF-31 on inputs before calling any LLM stage.
    """
    with get_connection() as conn:
        ctx = _fetch_clip_context(conn, clip_id, prompt_body="")
        input_rule_ids = {"PF-11", "PF-13", "PF-20", "PF-31"}
        violations: list[Violation] = []

        for rule in default_registry.list_rules():
            if rule.rule_id in input_rule_ids:
                violations.extend(rule.validate(ctx))

        return [v.to_dict() for v in violations]

@router.post("/clips/{clip_id}/preflight")
def run_preflight(clip_id: int, req: PreflightRequest = PreflightRequest()):
    """
    Run full preflight validator on prompt body (§9).
    Optionally runs deterministic autofix first if requested.
    """
    with get_connection() as conn:
        ctx = _fetch_clip_context(conn, clip_id, prompt_body=req.body)

        if req.run_autofix:
            fixed_body = run_deterministic_autofix(
                ctx.parsed_prompt.raw_body,
                audio_policy=ctx.clip.get("audio_policy", "dialogue_only"),
                mode=ctx.clip.get("mode", "T2VA"),
            )
            ctx.parsed_prompt = parse_prompt(fixed_body)

        violations = default_registry.validate_all(ctx)
        return [v.to_dict() for v in violations]

@router.post("/clips/{clip_id}/override")
def override_rule(clip_id: int, req: OverrideRequest):
    """
    Apply a manual override for a heuristic rule (§9.4):
    Only PF-04, PF-05, PF-10, PF-34 may be overridden with a mandatory note.
    """
    if req.rule_id not in ALLOWED_OVERRIDE_RULES:
        raise HTTPException(
            status_code=400,
            detail=f"Rule {req.rule_id} cannot be overridden. Only heuristic rules ({sorted(ALLOWED_OVERRIDE_RULES)}) may be overridden.",
        )

    if not req.note or not req.note.strip():
        raise HTTPException(
            status_code=400,
            detail="A mandatory explanation note is required to override a heuristic rule.",
        )

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM prompts WHERE clip_id = ? ORDER BY id DESC LIMIT 1", (clip_id,))
        prompt_row = cur.fetchone()
        if not prompt_row:
            raise HTTPException(status_code=404, detail="No prompt found for this clip to override.")

        prompt_id = prompt_row["id"]
        raw_ovr = prompt_row["overrides_json"]
        try:
            overrides_list = json.loads(raw_ovr)
            if isinstance(overrides_list, dict):
                overrides_list = [{"rule_id": k, **v} for k, v in overrides_list.items()]
            elif not isinstance(overrides_list, list):
                overrides_list = []
        except Exception:
            overrides_list = []

        # Remove existing override for this rule if any
        overrides_list = [o for o in overrides_list if o.get("rule_id") != req.rule_id]
        overrides_list.append({"rule_id": req.rule_id, "note": req.note.strip()})

        cur.execute(
            "UPDATE prompts SET overrides_json = ? WHERE id = ?",
            (json.dumps(overrides_list), prompt_id),
        )

        return {
            "status": "ok",
            "prompt_id": prompt_id,
            "rule_id": req.rule_id,
            "note": req.note.strip(),
            "overrides": overrides_list,
        }

@router.get("/vocab/{name}")
def get_vocabulary(name: str):
    """Serve bundled read-only JSON vocabularies and reference data (§1.5, Appendix A)."""
    allowed_vocabs = {
        "camera_moves": get_camera_moves,
        "mood_words": get_mood_words,
        "sound_lexicon": get_sound_lexicon,
        "scripts": get_scripts,
        "styles": get_styles,
        "voices": get_voices,
        "deliveries": get_deliveries,
        "shot_budgets": get_shot_budgets,
        "task_types": get_task_types,
        "retention_markers": get_retention_markers,
        "accents": get_accents,
    }

    loader = allowed_vocabs.get(name)
    if not loader:
        raise HTTPException(status_code=404, detail=f"Vocabulary '{name}' not found.")

    return loader()
