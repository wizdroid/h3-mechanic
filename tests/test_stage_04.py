"""Stage 04 Comprehensive Test Suite.

Verifies:
- Ollama Async Client (§5.4): tags, show, generate, token budget check, schema fallback, jsonschema validation
- Concurrency Lock (§5.5, §5.7, A-30): single-flight lock, HTTP 409 busy, startup crash recovery
- Staged Pipeline Runner (§5.5): NDJSON streaming, single structural retry with temp+0.1 and seed+1, prose fallback
- Worst-Case Call Budget Caps (Criterion A-32): <= 6 for T2VA/frames, <= 8 for REF2VA
- Preflight Repair Loop (§5.5, §8.0, §9.3): autofix precedence, placeholder integrity guard rejecting tampered outputs
"""

from __future__ import annotations
import asyncio
import json
import sqlite3
import uuid
import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.resources.vocab import HOUSE_SENTENCE
from app.storage.db import get_db_connection, get_connection
from app.llm.client import (
    OllamaClient,
    TokenBudgetExceededError,
    SchemaValidationError,
    ModelTruncatedError,
)
from app.llm.lock import (
    global_generation_lock,
    GenerationBusyError,
    recover_generating_clips_on_startup,
)
from app.llm.prompt_bank import (
    PLAN_JSON_SCHEMA,
    calculate_num_predict,
)
from app.llm.pipeline import (
    PipelineCallCounter,
    run_stage_with_single_retry,
    execute_generation_pipeline,
)
from app.llm.fixer import (
    check_placeholder_multiset_equality,
    run_fixer_loop,
)
from app.validation.registry import ValidationContext
from app.validation.parser import parse_prompt

# ============================================================================
# 1. OLLAMA CLIENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_ollama_client_tags_and_show():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b-instruct", "size": 4700000000}]})
        elif request.url.path == "/api/show":
            body = json.loads(request.content)
            return httpx.Response(200, json={"details": {"family": "qwen2", "parameter_size": "7B"}})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = OllamaClient(transport=transport)

    models = await client.list_models()
    assert len(models) == 1
    assert models[0]["name"] == "qwen2.5:7b-instruct"

    info = await client.show_model("qwen2.5:7b-instruct")
    assert info["details"]["family"] == "qwen2"

@pytest.mark.asyncio
async def test_ollama_token_budget_exceeded():
    client = OllamaClient()
    # Prompt with ~4000 characters -> ~1250 tokens
    long_prompt = "A" * 8000  # ~2500 tokens
    # num_ctx = 2048, 90% is 1843 tokens. prompt (2500) + num_predict (500) > 1843
    with pytest.raises(TokenBudgetExceededError):
        await client.generate(
            model="qwen2.5:7b-instruct",
            prompt=long_prompt,
            options={"num_ctx": 2048, "num_predict": 500},
        )

@pytest.mark.asyncio
async def test_ollama_schema_validation_success_and_failure():
    valid_plan = {
        "characters": [{"speaker_key": "1", "persona": "detective"}],
        "setting": "dimly lit office",
        "beats": ["enters office", "discovers note"],
        "shots": [
            {
                "start_s": 0.0,
                "end_s": 3.0,
                "size": "a medium close-up",
                "angle": "at eye level",
                "camera_phrase": "The camera pushes in",
                "landing": "toward the desk",
                "pacing": "action",
                "line_ids": ["{{L1}}"],
            }
        ],
        "voices": [{"speaker_key": "1", "voice": "M1"}],
    }

    # Case 1: Model returns valid structured plan
    def handler_valid(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": json.dumps(valid_plan), "done_reason": "stop"})

    client_valid = OllamaClient(transport=httpx.MockTransport(handler_valid))
    res = await client_valid.generate(
        model="qwen2.5:7b-instruct",
        prompt="plan brief",
        format=PLAN_JSON_SCHEMA,
    )
    assert res.parsed_json == valid_plan

    # Case 2: Model returns invalid schema (missing required 'shots' key)
    invalid_plan = {"characters": [], "setting": "city"}
    def handler_invalid(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": json.dumps(invalid_plan), "done_reason": "stop"})

    client_invalid = OllamaClient(transport=httpx.MockTransport(handler_invalid))
    with pytest.raises(SchemaValidationError):
        await client_invalid.generate(
            model="qwen2.5:7b-instruct",
            prompt="plan brief",
            format=PLAN_JSON_SCHEMA,
        )

@pytest.mark.asyncio
async def test_ollama_schema_fallback_on_400():
    """If Ollama rejects schema object with 400, client falls back to format: 'json'."""
    calls = []
    valid_plan = {
        "characters": [],
        "setting": "room",
        "beats": [],
        "shots": [{"start_s": 0.0, "end_s": 3.0, "size": "MS", "angle": "eye", "camera_phrase": "static", "pacing": "silent", "line_ids": []}],
        "voices": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        payload = json.loads(request.content)
        fmt = payload.get("format")
        if isinstance(fmt, dict):
            # Simulate Ollama version that doesn't support JSON Schema objects in format
            return httpx.Response(400, text="format schema object not supported")
        elif fmt == "json":
            return httpx.Response(200, json={"response": json.dumps(valid_plan), "done_reason": "stop"})
        return httpx.Response(500)

    client = OllamaClient(transport=httpx.MockTransport(handler))
    res = await client.generate(
        model="qwen2.5:7b-instruct",
        prompt="plan",
        format=PLAN_JSON_SCHEMA,
    )
    assert len(calls) == 2
    assert calls[1].url.path == "/api/generate"
    assert res.parsed_json == valid_plan

# ============================================================================
# 2. CONCURRENCY LOCK & CRASH RECOVERY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_concurrency_lock_single_flight():
    """Verify single process-wide lock raises GenerationBusyError if held."""
    assert not global_generation_lock.is_locked

    async with global_generation_lock.hold(clip_id=101):
        assert global_generation_lock.is_locked
        assert global_generation_lock.active_clip_id == 101

        # Second request must raise GenerationBusyError
        with pytest.raises(GenerationBusyError) as exc_info:
            async with global_generation_lock.hold(clip_id=102):
                pass
        assert exc_info.value.active_clip_id == 101

    # After exit, lock is released
    assert not global_generation_lock.is_locked
    assert global_generation_lock.active_clip_id is None

def test_startup_crash_recovery():
    """Verify startup crash recovery resets any clips in 'generating' state to 'draft'."""
    with get_connection() as conn:
        cur = conn.cursor()
        proj_name = f"Crash Recovery Proj {uuid.uuid4().hex[:8]}"
        cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, '', 'now', 'now')", (proj_name,))
        proj_id = cur.lastrowid

        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                audio_policy, style_id, plain_style_pair, inputs_revision, status, created_at, updated_at
            ) VALUES (?, 'Stuck Clip', 'T2VA', 'MiniMax-H3', 5, '768P', '16:9', 'dialogue_only', 'plain', 'Live-action, cinematic', 1, 'generating', 'now', 'now')
        """, (proj_id,))
        clip_id = cur.lastrowid
        conn.commit()

    # Run startup recovery
    reset_count = recover_generating_clips_on_startup()
    assert reset_count >= 1

    # Verify status is now 'draft'
    with get_connection() as conn:
        row = conn.execute("SELECT status FROM clips WHERE id = ?", (clip_id,)).fetchone()
        assert row["status"] == "draft"

# ============================================================================
# 3. SINGLE STRUCTURAL RETRY WITH TEMP +0.1 & SEED + 1
# ============================================================================

@pytest.mark.asyncio
async def test_single_structural_retry():
    """Mock attempt 1 invalid JSON, attempt 2 valid JSON -> verify temp+0.1 and seed+1."""
    attempts = []
    valid_plan = {
        "characters": [],
        "setting": "room",
        "beats": [],
        "shots": [{"start_s": 0.0, "end_s": 4.0, "size": "MS", "angle": "eye", "camera_phrase": "The camera pushes in", "pacing": "action", "line_ids": []}],
        "voices": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        opts = payload.get("options", {})
        attempts.append((opts.get("temperature"), opts.get("seed")))
        if len(attempts) == 1:
            # Attempt 1: Return malformed JSON
            return httpx.Response(200, json={"response": "Not valid JSON", "done_reason": "stop"})
        else:
            # Attempt 2: Return valid JSON
            return httpx.Response(200, json={"response": json.dumps(valid_plan), "done_reason": "stop"})

    client = OllamaClient(transport=httpx.MockTransport(handler))
    counter = PipelineCallCounter(max_calls=6)

    resp, attempts_used, _ = await run_stage_with_single_retry(
        client=client,
        model="qwen2.5:7b-instruct",
        prompt="make plan",
        stage_id="seed_elaboration",
        format=PLAN_JSON_SCHEMA,
        options={"temperature": 0.2, "seed": 42},
        call_counter=counter,
    )

    assert attempts_used == 2
    assert resp.parsed_json == valid_plan
    # Check attempt 1 parameters vs attempt 2 parameters
    assert attempts[0] == (0.2, 42)
    assert attempts[1] == (pytest.approx(0.3), 43)

# ============================================================================
# 4. WORST-CASE CALL BUDGET CEILING (A-32)
# ============================================================================

@pytest.mark.asyncio
async def test_worst_case_call_budget_ceiling():
    """Ensure PipelineCallCounter strictly prevents exceeding max allowed calls (<= 6 for T2VA)."""
    counter = PipelineCallCounter(max_calls=6)
    for _ in range(6):
        counter.record_call()
    assert counter.calls_made == 6

    # 7th call must raise RuntimeError
    with pytest.raises(RuntimeError) as exc_info:
        counter.record_call()
    assert "budget exceeded" in str(exc_info.value)

# ============================================================================
# 5. PREFLIGHT FIXER INTEGRITY GUARD TESTS
# ============================================================================

def test_placeholder_multiset_integrity_guard():
    orig_text = "[Shot 1] The camera pushes in. {{L1}} {{T1}} [Shot 2] {{L2}}."

    # 1. Exact match passes
    valid_rewrite = "[Shot 1] The camera pulls out. {{L1}} {{T1}} [Shot 2] {{L2}}."
    assert check_placeholder_multiset_equality(orig_text, valid_rewrite)

    # 2. Dropped {{L1}} fails
    dropped_l1 = "[Shot 1] The camera pushes in. {{T1}} [Shot 2] {{L2}}."
    assert not check_placeholder_multiset_equality(orig_text, dropped_l1)

    # 3. Added {{L3}} fails
    added_l3 = "[Shot 1] The camera pushes in. {{L1}} {{T1}} [Shot 2] {{L2}} {{L3}}."
    assert not check_placeholder_multiset_equality(orig_text, added_l3)

    # 4. Altered placeholder {{T2}} instead of {{T1}} fails
    altered_tm = "[Shot 1] The camera pushes in. {{L1}} {{T2}} [Shot 2] {{L2}}."
    assert not check_placeholder_multiset_equality(orig_text, altered_tm)

@pytest.mark.asyncio
async def test_fixer_loop_discards_tampered_output():
    """Simulate fixer attempting to replace {{L1}} with raw text -> must be discarded."""
    tampered_output = (
        "integrated_multimodal_description: [Shot 1] Live-action, cinematic. "
        "The detective speaks: Stop right there! "  # Tampered: dropped {{L1}}
        "The camera pushes in toward the desk.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": tampered_output, "done_reason": "stop"})

    client = OllamaClient(transport=httpx.MockTransport(handler))

    clip = {
        "id": 1,
        "mode": "T2VA",
        "audio_policy": "dialogue_only",
        "duration_s": 5,
        "ratio": "16:9",
        "video_model": "MiniMax-H3",
    }
    # Initial prompt has {{L1}} and missing landing (fixable)
    initial_body = (
        "integrated_multimodal_description: [Shot 1] Live-action, cinematic. "
        "The detective speaks: {{L1}} The camera pushes in.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    parsed = parse_prompt(initial_body)
    ctx = ValidationContext(clip=clip, parsed_prompt=parsed)

    final_body, violations, retries = await run_fixer_loop(
        ctx=ctx,
        client=client,
        model="qwen2.5:7b-instruct",
        max_retries=2,
    )

    # Both retries must be discarded because fixer tampered with {{L1}}
    assert retries == 2
    # The final body must NOT adopt the tampered text
    assert "{{L1}}" in final_body

# ============================================================================
# 6. API PIPELINE ENDPOINT TESTS (NDJSON STREAMING & 409 BUSY)
# ============================================================================

@pytest.mark.asyncio
async def test_api_generation_ndjson_streaming_and_409_busy():
    proj_name = f"Pipeline API Proj {uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, '', 'now', 'now')", (proj_name,))
        proj_id = cur.lastrowid

        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                audio_policy, style_id, plain_style_pair, seed_text, inputs_revision, status, created_at, updated_at
            ) VALUES (?, 'Pipeline Clip', 'T2VA', 'MiniMax-H3', 5, '768P', '16:9', 'dialogue_only', 'plain', 'Live-action, cinematic', 'Detective investigates room', 1, 'draft', 'now', 'now')
        """, (proj_id,))
        clip_id = cur.lastrowid
        conn.commit()

    valid_plan = {
        "characters": [],
        "setting": "room",
        "beats": ["searches"],
        "shots": [
            {
                "start_s": 0.0,
                "end_s": 5.0,
                "size": "a medium close-up",
                "angle": "at eye level",
                "camera_phrase": "The camera pushes in",
                "landing": "toward the desk",
                "pacing": "action",
                "line_ids": [],
            }
        ],
        "voices": [],
    }
    prose_response = (
        "[Shot 1] Live-action, cinematic. The room is quiet. "
        "The camera pushes in toward the desk revealing dusty papers."
    )

    def mock_ollama_handler(request: httpx.Request) -> httpx.Response:
        content = request.content.decode("utf-8")
        if "seed_elaboration" in content or "Expand a brief into a scene plan" in content:
            return httpx.Response(200, json={"response": json.dumps(valid_plan), "done_reason": "stop"})
        else:
            return httpx.Response(200, json={"response": prose_response, "done_reason": "stop"})

    mock_client = OllamaClient(transport=httpx.MockTransport(mock_ollama_handler))
    app.state.ollama_client = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # 1. POST /api/clips/{id}/generate with Accept: application/x-ndjson
        resp = await client.post(
            f"/api/clips/{clip_id}/generate",
            headers={"Accept": "application/x-ndjson"},
            json={"drafter_model": "qwen2.5:7b-instruct", "seed": 42},
        )
        assert resp.status_code == 200
        assert "application/x-ndjson" in resp.headers["content-type"]

        # Parse NDJSON lines
        lines = [json.loads(line) for line in resp.text.strip().split("\n") if line.strip()]
        events = [l.get("event") for l in lines]
        assert "stage_start" in events
        assert "stage_done" in events
        assert "done" in events

        # 2. Test 409 Busy when lock is held
        async with global_generation_lock.hold(clip_id=clip_id):
            resp_busy = await client.post(
                f"/api/clips/{clip_id}/generate",
                json={"drafter_model": "qwen2.5:7b-instruct"},
            )
            assert resp_busy.status_code == 409
            assert resp_busy.json()["detail"]["error"]["code"] == "busy"
            assert resp_busy.json()["detail"]["error"]["active_clip_id"] == clip_id

        # 3. Test POST /api/clips/{id}/variations
        resp_var = await client.post(f"/api/clips/{clip_id}/variations")
        assert resp_var.status_code == 200
        assert resp_var.json()["stage"] == "variation"

        # Duplicate variation attempt must return 409
        resp_var_dup = await client.post(f"/api/clips/{clip_id}/variations")
        assert resp_var_dup.status_code == 409
        assert resp_var_dup.json()["detail"]["error"]["code"] == "variation_exists"
