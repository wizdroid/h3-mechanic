"""Stage 05 Comprehensive Test Suite: Generator Web Shell & T2VA Mode.

Verifies:
1. Static Asset Delivery (§4.1–§4.3):
   - GET / (index.html), GET /css/nord.css, GET /js/app.js, GET /js/modes/t2va.js
2. Modes Registry & Settings (§4.3, §4.4.7):
   - GET /api/modes returns 5 modes with T2VA concrete ratio
   - GET /api/voices and GET /api/settings
3. T2VA End-to-End Generation (§7.2, §8.1, Criterion A-01):
   - Valid 3-field output with single lines and blank lines between
   - Dialogue-only house sentence placed in [Shot 1]
4. Fallback Prose Stitcher (S-05, §8.1b):
   - Triggered when prose writer fails twice
   - prompts.prose_fallback == 1 and clip status is 'preflight'
   - Preserves all planned {{Lk}} placeholders without omission
5. Stage 0 Zero-Ollama Guard (Criterion A-29):
   - Rejects pure Romanized Indic dialogue with HTTP 422
   - Rejects adaptive ratio for T2VA with HTTP 422
   - Asserts exactly ZERO Ollama requests made
"""

from __future__ import annotations
import json
import sqlite3
import uuid
import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.resources.vocab import HOUSE_SENTENCE
from app.storage.db import get_connection
from app.llm.client import OllamaClient


# ==============================================================================
# 1. STATIC ASSET & WEB SHELL TESTS (§4.1–§4.3, Criterion A-22, A-23)
# ==============================================================================

@pytest.mark.asyncio
async def test_static_assets_delivery():
    """Verify index.html, nord.css, and ES JS modules load cleanly with status 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # 1. GET / (index.html)
        resp_index = await client.get("/")
        assert resp_index.status_code == 200
        assert "text/html" in resp_index.headers["content-type"]
        assert "H3 PROMPT STUDIO" in resp_index.text
        assert 'href="/css/nord.css"' in resp_index.text
        assert 'src="/js/app.js"' in resp_index.text

        # 2. GET /css/nord.css
        resp_css = await client.get("/css/nord.css")
        assert resp_css.status_code == 200
        assert "text/css" in resp_css.headers["content-type"]
        assert "--nord0: #2e3440;" in resp_css.text
        assert "nord-dark" in resp_css.text
        assert "nord-coloured" in resp_css.text
        assert "nord-light" in resp_css.text
        assert ".prompt-preview" in resp_css.text

        # 3. GET /js/app.js
        resp_app_js = await client.get("/js/app.js")
        assert resp_app_js.status_code == 200
        assert "AppController" in resp_app_js.text
        assert "renderT2VAForm" in resp_app_js.text

        # 4. GET /js/modes/t2va.js
        resp_t2va_js = await client.get("/js/modes/t2va.js")
        assert resp_t2va_js.status_code == 200
        assert "export function renderT2VAForm" in resp_t2va_js.text


# ==============================================================================
# 2. MODES REGISTRY & SETTINGS API TESTS (§4.3, §4.4.7, §5.6)
# ==============================================================================

@pytest.mark.asyncio
async def test_modes_registry_and_settings_endpoints():
    """Verify modes registry metadata and settings endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # GET /api/modes
        resp_modes = await client.get("/api/modes")
        assert resp_modes.status_code == 200
        modes = resp_modes.json()
        mode_ids = [m["id"] for m in modes]
        assert "T2VA" in mode_ids
        assert "I2VA" in mode_ids
        assert "FL2VA" in mode_ids
        assert "L2VA" in mode_ids
        assert "REF2VA" in mode_ids

        # Verify T2VA ratio policy is concrete (§4.4.1)
        t2va_meta = next(m for m in modes if m["id"] == "T2VA")
        assert t2va_meta["ratio_policy"] == "concrete"
        assert "adaptive" not in t2va_meta["allowed_ratios"]
        assert "16:9" in t2va_meta["allowed_ratios"]

        # GET /api/voices
        resp_voices = await client.get("/api/voices")
        assert resp_voices.status_code == 200
        voices = resp_voices.json()
        assert "F1" in voices
        assert "M1" in voices
        assert "K1" in voices

        # GET /api/settings
        resp_settings = await client.get("/api/settings")
        assert resp_settings.status_code == 200
        settings = resp_settings.json()
        assert settings["theme"] in ("nord-dark", "nord-coloured", "nord-light")
        assert settings["default_ratio"] == "16:9"


# ==============================================================================
# 3. T2VA END-TO-END GENERATION (§7.2, §8.1, Criterion A-01)
# ==============================================================================

@pytest.mark.asyncio
async def test_t2va_end_to_end_generation():
    """
    Test T2VA pipeline execution end-to-end:
    - seed_text: 'A detective walks into an abandoned warehouse in the rain'
    - Output format: exactly 3 fields on single lines, blank line between
    - Dialogue-only house audio sentence inserted in [Shot 1]
    - Status set to 'preflight'
    """
    proj_name = f"T2VA Proj {uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, '', 'now', 'now')", (proj_name,))
        proj_id = cur.lastrowid

        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                audio_policy, style_id, plain_style_pair, seed_text, inputs_revision, status, created_at, updated_at
            ) VALUES (?, 'Detective Warehouse', 'T2VA', 'MiniMax-H3', 5, '768P', '16:9', 'dialogue_only', 'plain', 'Live-action, cinematic', 'A detective walks into an abandoned warehouse in the rain', 1, 'draft', 'now', 'now')
        """, (proj_id,))
        clip_id = cur.lastrowid
        conn.commit()

    valid_plan = {
        "characters": [],
        "setting": "an abandoned warehouse in the rain",
        "beats": ["enters", "searches", "spots clue"],
        "shots": [
            {
                "start_s": 0.0,
                "end_s": 5.0,
                "size": "a medium wide shot",
                "angle": "at eye level",
                "camera_phrase": "The camera pushes in",
                "landing": "toward the rusted doorway",
                "pacing": "action",
                "line_ids": [],
            }
        ],
        "voices": [],
    }
    prose_response = (
        "[Shot 1] Live-action, cinematic. Shadows stretch across the corrugated siding of the warehouse. "
        "The camera pushes in toward the rusted doorway revealing damp puddles on the concrete floor."
    )

    ollama_calls = []

    def mock_ollama_handler(request: httpx.Request) -> httpx.Response:
        ollama_calls.append(request)
        content = request.content.decode("utf-8")
        if "seed_elaboration" in content or "Expand a brief into a scene plan" in content:
            return httpx.Response(200, json={"response": json.dumps(valid_plan), "done_reason": "stop"})
        else:
            return httpx.Response(200, json={"response": prose_response, "done_reason": "stop"})

    mock_client = OllamaClient(transport=httpx.MockTransport(mock_ollama_handler))
    app.state.ollama_client = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        resp = await client.post(
            f"/api/clips/{clip_id}/generate",
            json={"drafter_model": "qwen2.5:7b-instruct", "seed": 42},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event"] == "done"
        assert data["status"] == "preflight"

    # Verify Database Prompt Record and Output Contract (§7.2, §7.6)
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM prompts WHERE clip_id = ?", (clip_id,))
        prompt = dict(cur.fetchone())
        cur.execute("SELECT status FROM clips WHERE id = ?", (clip_id,))
        clip_status = cur.fetchone()["status"]

    assert clip_status == "preflight"
    assert prompt["prose_fallback"] == 0

    body = prompt["body"]

    # 1. Exactly 3 fields separated by blank lines (§7.2, §7.6)
    fields = [s.strip() for s in body.split("\n\n") if s.strip()]
    assert len(fields) == 3

    assert fields[0].startswith("integrated_multimodal_description: [Shot 1] Live-action, cinematic.")
    assert fields[1] == "overall_soundscape: N/A"
    assert fields[2] == "non_diegetic_music: N/A"

    # 2. Dialogue-only house sentence placed immediately after first sentence of [Shot 1]
    assert HOUSE_SENTENCE in fields[0]


# ==============================================================================
# 4. PROSE FALLBACK VERIFICATION (S-05, §8.1b)
# ==============================================================================

@pytest.mark.asyncio
async def test_t2va_prose_fallback_on_writer_failure():
    """
    Test fallback prose stitcher:
    - Ollama prose_writer fails twice with error responses
    - Pipeline engages stitch_fallback_prose and sets prose_fallback == 1
    - Status is 'preflight'
    - Dialogue placeholder {{L1}} is preserved and rendered into final body
    """
    proj_name = f"Fallback Proj {uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, '', 'now', 'now')", (proj_name,))
        proj_id = cur.lastrowid

        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                audio_policy, style_id, plain_style_pair, seed_text, inputs_revision, status, created_at, updated_at
            ) VALUES (?, 'Fallback Clip', 'T2VA', 'MiniMax-H3', 5, '768P', '16:9', 'dialogue_only', 'plain', 'Live-action, cinematic', 'Officer interrogates suspect', 1, 'draft', 'now', 'now')
        """, (proj_id,))
        clip_id = cur.lastrowid

        # Attach speaker and dialogue line
        cur.execute("""
            INSERT INTO speakers (clip_id, display_name, persona, voice_source, accent, pronoun, created_at, updated_at)
            VALUES (?, 'Officer', 'the police officer', 'F1', '', 'his', 'now', 'now')
        """, (clip_id,))
        spk_id = cur.lastrowid

        cur.execute("""
            INSERT INTO dialogue_lines (
                clip_id, line_order, speaker_id, language, text_raw, gloss, delivery,
                is_voiceover, cutoff, crosses_cut, created_at, updated_at
            ) VALUES (?, 1, ?, 'English', 'Tell me everything you saw!', '', 'command', 0, 0, 0, 'now', 'now')
        """, (clip_id, spk_id))
        conn.commit()

    valid_plan = {
        "characters": [{"speaker_key": str(spk_id), "persona": "the police officer"}],
        "setting": "interrogation room",
        "beats": ["confrontation"],
        "shots": [
            {
                "start_s": 0.0,
                "end_s": 5.0,
                "size": "a medium close-up",
                "angle": "front-facing",
                "camera_phrase": "The camera pushes in",
                "landing": "toward the table",
                "pacing": "action",
                "line_ids": ["1"],
            }
        ],
        "voices": [{"speaker_key": str(spk_id), "voice": "F1"}],
    }

    def mock_ollama_handler(request: httpx.Request) -> httpx.Response:
        content = request.content.decode("utf-8")
        if "seed_elaboration" in content or "Expand a brief into a scene plan" in content:
            return httpx.Response(200, json={"response": json.dumps(valid_plan), "done_reason": "stop"})
        else:
            # Force prose_writer to fail!
            return httpx.Response(500, text="Internal Drafter Error")

    mock_client = OllamaClient(transport=httpx.MockTransport(mock_ollama_handler))
    app.state.ollama_client = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        resp = await client.post(
            f"/api/clips/{clip_id}/generate",
            json={"drafter_model": "qwen2.5:7b-instruct", "seed": 100},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["event"] == "done"
        assert data["status"] == "preflight"

    # Verify Fallback Prose Behavior
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM prompts WHERE clip_id = ?", (clip_id,))
        prompt = dict(cur.fetchone())
        cur.execute("SELECT status FROM clips WHERE id = ?", (clip_id,))
        clip_status = cur.fetchone()["status"]

    assert clip_status == "preflight"
    assert prompt["prose_fallback"] == 1, "prompts.prose_fallback must be 1 when fallback prose is engaged"

    body = prompt["body"]
    assert "integrated_multimodal_description:" in body
    # Verify dialogue line was rendered from the stitched placeholder without omission
    assert "Tell me everything you saw!" in body
    assert HOUSE_SENTENCE in body


# ==============================================================================
# 5. STAGE 0 ZERO-OLLAMA REJECTION GUARDS (Criterion A-29)
# ==============================================================================

@pytest.mark.asyncio
async def test_stage_0_rejection_makes_zero_ollama_calls():
    """
    Criterion A-29:
    - Pure Romanized Indic dialogue line (e.g. Kannada line 'Bega ba') fails PF-31
    - Adaptive ratio in T2VA fails PF-11
    - Immediately returns HTTP 422 with ZERO Ollama calls
    """
    proj_name = f"Stage0 Guard Proj {uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, '', 'now', 'now')", (proj_name,))
        proj_id = cur.lastrowid

        # 1. Clip with invalid purely romanized Kannada line ("Bega ba")
        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                audio_policy, style_id, plain_style_pair, seed_text, inputs_revision, status, created_at, updated_at
            ) VALUES (?, 'Romanized Indic Clip', 'T2VA', 'MiniMax-H3', 5, '768P', '16:9', 'dialogue_only', 'plain', 'Live-action, cinematic', 'Test brief', 1, 'draft', 'now', 'now')
        """, (proj_id,))
        clip_romanized_id = cur.lastrowid

        cur.execute("""
            INSERT INTO speakers (clip_id, display_name, persona, voice_source, accent, pronoun, created_at, updated_at)
            VALUES (?, 'Speaker 1', 'the character', 'F1', '', 'his', 'now', 'now')
        """, (clip_romanized_id,))
        spk_rom_id = cur.lastrowid

        cur.execute("""
            INSERT INTO dialogue_lines (
                clip_id, line_order, speaker_id, language, text_raw, gloss, delivery,
                is_voiceover, cutoff, crosses_cut, created_at, updated_at
            ) VALUES (?, 1, ?, 'Kannada', 'Bega ba', 'Come quickly', 'none', 0, 0, 0, 'now', 'now')
        """, (clip_romanized_id, spk_rom_id))

        conn.commit()

    ollama_request_count = 0

    def mock_ollama_counting_handler(request: httpx.Request) -> httpx.Response:
        nonlocal ollama_request_count
        ollama_request_count += 1
        return httpx.Response(200, json={"response": "{}", "done_reason": "stop"})

    mock_client = OllamaClient(transport=httpx.MockTransport(mock_ollama_counting_handler))
    app.state.ollama_client = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # Case A: Purely romanized Kannada dialogue -> must return HTTP 422
        resp_rom = await client.post(f"/api/clips/{clip_romanized_id}/generate")
        assert resp_rom.status_code == 422
        err_rom = resp_rom.json()
        assert err_rom["detail"]["error"]["code"] == "stage_0"
        rule_ids = [v["rule_id"] for v in err_rom["detail"]["error"]["violations"]]
        assert "PF-31" in rule_ids
        assert ollama_request_count == 0, "Ollama request count must be strictly 0"

        # Case B: Adaptive ratio for T2VA rejected by API validation with HTTP 422
        resp_adapt = await client.post(
            f"/api/projects/{proj_id}/clips",
            json={"mode": "T2VA", "ratio": "adaptive", "duration_s": 8},
        )
        assert resp_adapt.status_code == 422
        assert "concrete ratio" in resp_adapt.text
        assert ollama_request_count == 0, "Ollama request count must remain strictly 0"
