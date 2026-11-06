"""LLM API routes: generation, models, warmup, fix, variations, and cancel (§5.5, §5.6)."""

from __future__ import annotations
import json
import sqlite3
from typing import Any, Optional
from urllib.parse import unquote
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.storage.db import get_connection
from app.llm.client import OllamaClient
from app.llm.lock import global_generation_lock, GenerationBusyError
from app.llm.pipeline import execute_generation_pipeline
from app.llm.fixer import run_fixer_loop
from app.llm.prompt_bank import SAFER_FRAMING_PROMPT, calculate_num_predict
from app.validation.registry import default_registry, ValidationContext
from app.validation.parser import parse_prompt
from app.api.validation_routes import _fetch_clip_context

router = APIRouter(prefix="/api", tags=["llm"])

# In-memory cached model list from GET /api/tags
_MODEL_CACHE: list[dict[str, Any]] = []

def get_ollama_client(request: Request) -> OllamaClient:
    """Helper to instantiate OllamaClient from app state or default."""
    client = getattr(request.app.state, "ollama_client", None)
    if client is None:
        client = OllamaClient()
    return client

class GenerateRequest(BaseModel):
    drafter_model: Optional[str] = None
    seed: Optional[int] = None

class SelectPromptRequest(BaseModel):
    prompt_id: int

@router.get("/models")
async def list_models(request: Request):
    """GET /api/models - prefetch GET /api/tags from local Ollama (§5.6.1)."""
    global _MODEL_CACHE
    client = get_ollama_client(request)
    try:
        models = await client.list_models()
        _MODEL_CACHE = models
        return models
    except Exception as e:
        if _MODEL_CACHE:
            return _MODEL_CACHE
        return []

@router.get("/models/{name:path}")
async def get_model_info(name: str, request: Request):
    """GET /api/models/{name} - calls POST /api/show on local Ollama."""
    decoded_name = unquote(name)
    client = get_ollama_client(request)
    try:
        return await client.show_model(decoded_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Model '{decoded_name}' not found: {str(e)}")

@router.post("/clips/{clip_id}/warmup")
async def warmup_drafter(clip_id: int, request: Request):
    """
    POST /api/clips/{id}/warmup - cheap drafter warm-up call (num_predict: 1).
    Takes generation lock; skips if lock held; non-blocking (§5.5).
    """
    if global_generation_lock.is_locked:
        return {"status": "skipped", "reason": "lock_held"}

    client = get_ollama_client(request)
    try:
        async with global_generation_lock.hold(clip_id):
            await client.generate(
                model="qwen2.5:7b-instruct",
                prompt="ready",
                options={"num_predict": 1},
                timeout=15.0,
            )
        return {"status": "ok"}
    except Exception:
        return {"status": "skipped", "reason": "warmup_failed"}

@router.post("/clips/{clip_id}/generate")
async def generate_prompt(clip_id: int, request: Request, req: GenerateRequest = GenerateRequest()):
    """
    POST /api/clips/{id}/generate - run mode generation pipeline (§5.5).
    Runs Stage 0 validation before lock or streaming; fails fast with HTTP 422 if invalid.
    Streams progress using NDJSON when Accept: application/x-ndjson header is present.
    Enforces process-wide single-flight lock (HTTP 409 busy).
    """
    # 1. Stage 0 Input Validation (§5.5, Criterion A-29)
    # Zero Ollama calls, zero lock acquisition on failure
    with get_connection() as conn:
        ctx = _fetch_clip_context(conn, clip_id, prompt_body="")
        input_rule_ids = {"PF-11", "PF-13", "PF-20", "PF-31"}
        violations = []
        for rule in default_registry.list_rules():
            if rule.rule_id in input_rule_ids:
                violations.extend(rule.validate(ctx))
        blocking_stage0 = [v for v in violations if v.blocking]
        if blocking_stage0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": "stage_0",
                        "message": f"Stage 0 input validation failed with {len(blocking_stage0)} blocking errors.",
                        "violations": [v.to_dict() for v in blocking_stage0],
                    }
                },
            )

    # 2. Concurrency Lock check (§5.5, §5.7)
    if global_generation_lock.is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "busy",
                    "message": f"Generation engine is busy with clip {global_generation_lock.active_clip_id}",
                    "active_clip_id": global_generation_lock.active_clip_id,
                }
            },
        )

    # Resolve drafter model
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = 'drafter_model'")
        row = cur.fetchone()
        stored_drafter = row["value"] if row else "qwen2.5:7b-instruct"

    drafter = req.drafter_model or stored_drafter
    client = get_ollama_client(request)

    async def _locked_stream():
        async with global_generation_lock.hold(clip_id):
            async for chunk in execute_generation_pipeline(
                clip_id=clip_id,
                client=client,
                drafter_model=drafter,
                seed_override=req.seed,
            ):
                yield chunk

    accept_header = request.headers.get("Accept", "")
    if "application/x-ndjson" in accept_header or "ndjson" in accept_header:
        return StreamingResponse(_locked_stream(), media_type="application/x-ndjson")

    # If non-streaming requested, consume all NDJSON chunks and return final event
    final_event = {}
    async for chunk in _locked_stream():
        try:
            line_obj = json.loads(chunk.strip())
            if line_obj.get("event") in ("done", "error"):
                final_event = line_obj
        except Exception:
            pass

    return final_event

@router.post("/clips/{clip_id}/generate/cancel")
async def cancel_generation(clip_id: int):
    """POST /api/clips/{id}/generate/cancel - cancel in-flight generation (§5.5)."""
    if global_generation_lock.active_clip_id == clip_id:
        # Releasing the lock resets the state
        with get_connection() as conn:
            conn.execute("UPDATE clips SET status = 'draft' WHERE id = ?", (clip_id,))
            conn.commit()
        return {"status": "cancelled", "clip_id": clip_id}
    return {"status": "not_generating", "clip_id": clip_id}

@router.post("/clips/{clip_id}/fix")
async def run_fixer(clip_id: int, request: Request):
    """POST /api/clips/{id}/fix - run fixer loop (§5.5, §9.3)."""
    if global_generation_lock.is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "busy",
                    "message": f"Generation lock is busy with clip {global_generation_lock.active_clip_id}",
                    "active_clip_id": global_generation_lock.active_clip_id,
                }
            },
        )

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        clip = dict(cur.fetchone())
        cur.execute("SELECT * FROM prompts WHERE clip_id = ? ORDER BY id DESC LIMIT 1", (clip_id,))
        prompt_row = cur.fetchone()
        if not prompt_row:
            raise HTTPException(status_code=404, detail="No prompt to fix")
        prompt = dict(prompt_row)

    client = get_ollama_client(request)
    parsed = parse_prompt(prompt["body"])
    ctx = ValidationContext(clip=clip, parsed_prompt=parsed, prompt=prompt)

    async with global_generation_lock.hold(clip_id):
        fixed_body, remaining_violations, retries = await run_fixer_loop(
            ctx=ctx,
            client=client,
            model=prompt.get("drafter_model") or "qwen2.5:7b-instruct",
            max_retries=2,
            seed=prompt.get("ollama_seed", 42),
        )

    # Save fixed prompt
    status_label = "fixed" if not any(v.blocking for v in remaining_violations) else "blocked"
    with get_connection() as conn:
        conn.execute("""
            UPDATE prompts
            SET body = ?, preflight_json = ?, fixer_retries = fixer_retries + ?
            WHERE id = ?
        """, (fixed_body, json.dumps([v.to_dict() for v in remaining_violations]), retries, prompt["id"]))
        conn.execute("UPDATE clips SET status = ? WHERE id = ?", (status_label, clip_id))
        conn.commit()

    return {
        "status": status_label,
        "clip_id": clip_id,
        "retries_used": retries,
        "violations": [v.to_dict() for v in remaining_violations],
    }

@router.post("/clips/{clip_id}/variations")
async def generate_variation(clip_id: int, request: Request):
    """
    POST /api/clips/{id}/variations - one safer-framing variation per draft (§8.9).
    Returns 409 Conflict if a variation already exists in the same generation_id.
    """
    if global_generation_lock.is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "busy", "active_clip_id": global_generation_lock.active_clip_id}},
        )

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        clip = dict(cur.fetchone())

        cur.execute("SELECT * FROM prompts WHERE clip_id = ? AND stage = 'draft' ORDER BY id DESC LIMIT 1", (clip_id,))
        draft_prompt = cur.fetchone()
        if not draft_prompt:
            raise HTTPException(status_code=404, detail="No draft prompt found to create variation from")
        draft = dict(draft_prompt)

        # Check if variation already exists for this generation_id
        cur.execute("SELECT id FROM prompts WHERE generation_id = ? AND stage = 'variation'", (draft["generation_id"],))
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "variation_exists", "message": "A variation already exists for this draft generation."}},
            )

    client = get_ollama_client(request)
    mode = clip.get("mode", "T2VA")
    prompt_text = SAFER_FRAMING_PROMPT.format(mode=mode)
    num_predict = calculate_num_predict("safer_framing", {"template_text": draft["body_template"]})

    async with global_generation_lock.hold(clip_id):
        resp = await client.generate(
            model=draft.get("drafter_model") or "qwen2.5:7b-instruct",
            prompt=f"{prompt_text}\n\nTemplate:\n{draft['body_template']}",
            options={"temperature": 0.2, "seed": draft.get("ollama_seed", 42), "num_predict": num_predict},
        )
        variation_body = resp.response_text.strip()

    # Save variation prompt
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO prompts (
                clip_id, generation_id, stage, inputs_revision, body_template,
                body, char_count, structured_payload_json, preflight_json, overrides_json,
                drafter_model, ollama_seed, created_at
            ) VALUES (?, ?, 'variation', ?, ?, ?, ?, ?, '[]', '[]', ?, ?, datetime('now'))
        """, (
            clip_id,
            draft["generation_id"],
            clip["inputs_revision"],
            variation_body,
            variation_body,
            len(variation_body),
            draft.get("structured_payload_json"),
            draft.get("drafter_model"),
            draft.get("ollama_seed"),
        ))
        var_prompt_id = cur.lastrowid
        conn.commit()

    return {"status": "ok", "prompt_id": var_prompt_id, "stage": "variation"}

@router.post("/clips/{clip_id}/select")
def select_prompt(clip_id: int, req: SelectPromptRequest):
    """POST /api/clips/{id}/select - choose draft or variation as export source (§5.6)."""
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id FROM prompts WHERE id = ? AND clip_id = ?", (req.prompt_id, clip_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Prompt not found for this clip")

        cur.execute("UPDATE clips SET selected_prompt_id = ? WHERE id = ?", (req.prompt_id, clip_id))
        conn.commit()
        return {"status": "ok", "clip_id": clip_id, "selected_prompt_id": req.prompt_id}
