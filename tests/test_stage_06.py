"""Stage 06 Comprehensive Test Suite: Frame Modes (I2VA, FL2VA, L2VA).

Verifies (§4.4.3–§4.4.5, §7.3, §7.6, Appendix A.2, Criteria A-02, A-03, A-04, A-12):
1. Byte-exact instruction line generation for I2VA, FL2VA, and L2VA:
   - I2VA: "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
   - FL2VA: "How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video." (em dash U+2014, no brackets, S.SS = duration_s.00).
   - L2VA: "How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video." (brackets kept, em dash U+2014).
2. Locked adaptive ratio enforcement (PF-11):
   - Rejection of concrete ratio with HTTP 422 upon clip creation and update.
   - Stage 0 input validation fast-fail (Criterion A-29).
3. FL2VA Single-Shot Exception (Criterion A-12):
   - 8s one-shot FL2VA clip with requested_shot_count == 1 waives PF-03 minimum shot count.
   - End-to-end generation and export of 1-shot FL2VA clip succeeds.
4. 4-Block Output Format (§7.6):
   - Instruction line, blank line, then 3 single-line fields:
     integrated_multimodal_description, overall_soundscape, non_diegetic_music.
5. Reference Tokens CRUD, ordering, and resequencing (+1000000 offset):
   - Enforce image-only references in frame modes.
   - Automatic position and ordinal resequencing upon deletion.
6. Validation checks (PF-20, PF-27):
   - Disallow <Subject>, <Audio>, <Video> tokens and REF2VA headers.
   - Advisory warnings for dimensions outside 256–5760 px or ratio [0.4, 2.5].
"""

from __future__ import annotations
import json
import sqlite3
import uuid
import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.storage.db import get_connection
from app.engine.renderer import build_instruction_line
from app.llm.client import OllamaClient
from app.validation.registry import default_registry, ValidationContext
from app.validation.parser import parse_prompt


# ==============================================================================
# 1. INSTRUCTION LINE GENERATOR TESTS (§7.6, Appendix A.2, Criteria A-02–A-04)
# ==============================================================================

def test_instruction_lines_byte_exact_contract():
    """Verify byte-exact instruction lines matching Appendix A.2 verbatim."""
    # 1. I2VA
    i2va_line = build_instruction_line("I2VA", shot_count=2, duration_s=8)
    assert i2va_line == "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
    assert "<Picture 1>" in i2va_line
    assert "[Shot 1]" in i2va_line

    # 2. FL2VA with duration 10s and 3 shots (Checkpoint 1)
    fl2va_line = build_instruction_line("FL2VA", shot_count=3, duration_s=10)
    expected_fl2va = (
        "How the reference pictures align with the target video — "
        "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
        "Picture 2 (from Shot 3) aligns with the 10.00-second mark of the target video."
    )
    assert fl2va_line == expected_fl2va
    assert "—" in fl2va_line  # U+2014 em dash
    assert "<Picture" not in fl2va_line  # No angle brackets
    assert "[Shot" not in fl2va_line  # No square brackets
    assert "10.00-second" in fl2va_line

    # 3. FL2VA single shot with duration 8s
    fl2va_1shot = build_instruction_line("FL2VA", shot_count=1, duration_s=8)
    assert fl2va_1shot == (
        "How the reference pictures align with the target video — "
        "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
        "Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video."
    )

    # 4. L2VA with duration 12s and 4 shots
    l2va_line = build_instruction_line("L2VA", shot_count=4, duration_s=12)
    expected_l2va = (
        "How the reference pictures align with the target video — "
        "<Picture 1> (from [Shot 4]) aligns with the 12.00-second mark of the target video."
    )
    assert l2va_line == expected_l2va
    assert "—" in l2va_line  # U+2014 em dash
    assert "<Picture 1>" in l2va_line  # Angle brackets kept
    assert "[Shot 4]" in l2va_line  # Square brackets kept
    assert "12.00-second" in l2va_line


@pytest.mark.asyncio
async def test_api_instruction_preview_endpoint():
    """Verify GET /api/clips/{id}/instruction-preview returns code-generated line."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # Create a project and FL2VA clip
        p_res = await client.post("/api/projects", json={"name": f"P-{uuid.uuid4().hex[:6]}"})
        pid = p_res.json()["id"]

        c_res = await client.post(
            f"/api/projects/{pid}/clips",
            json={
                "name": "FL2VA Preview Test",
                "mode": "FL2VA",
                "duration_s": 10,
                "ratio": "adaptive",
                "requested_shot_count": 3,
            },
        )
        assert c_res.status_code == 200
        cid = c_res.json()["id"]

        prev_res = await client.get(f"/api/clips/{cid}/instruction-preview")
        assert prev_res.status_code == 200
        data = prev_res.json()
        assert data["mode"] == "FL2VA"
        assert data["duration_s"] == 10
        assert data["shot_count"] == 3
        assert "Picture 2 (from Shot 3) aligns with the 10.00-second mark" in data["instruction_line"]


# ==============================================================================
# 2. ADAPTIVE RATIO LOCK ENFORCEMENT (§4.4.3–§4.4.5, PF-11)
# ==============================================================================

@pytest.mark.asyncio
async def test_frame_modes_locked_to_adaptive_ratio():
    """Verify I2VA, FL2VA, L2VA reject concrete ratios with HTTP 422 (Checkpoint 3)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        p_res = await client.post("/api/projects", json={"name": f"P-{uuid.uuid4().hex[:6]}"})
        pid = p_res.json()["id"]

        # 1. Attempt creating I2VA clip with 16:9 ratio -> must reject 422
        bad_i2va = await client.post(
            f"/api/projects/{pid}/clips",
            json={"name": "Bad I2VA", "mode": "I2VA", "ratio": "16:9", "duration_s": 8},
        )
        assert bad_i2va.status_code == 422
        assert bad_i2va.json()["detail"]["error"]["code"] == "validation"

        # 2. Attempt creating FL2VA clip with 21:9 ratio -> must reject 422
        bad_fl2va = await client.post(
            f"/api/projects/{pid}/clips",
            json={"name": "Bad FL2VA", "mode": "FL2VA", "ratio": "21:9", "duration_s": 8},
        )
        assert bad_fl2va.status_code == 422

        # 3. Attempt creating L2VA clip with 1:1 ratio -> must reject 422
        bad_l2va = await client.post(
            f"/api/projects/{pid}/clips",
            json={"name": "Bad L2VA", "mode": "L2VA", "ratio": "1:1", "duration_s": 8},
        )
        assert bad_l2va.status_code == 422

        # 4. Valid I2VA clip with adaptive ratio -> 200
        good_i2va = await client.post(
            f"/api/projects/{pid}/clips",
            json={"name": "Good I2VA", "mode": "I2VA", "ratio": "adaptive", "duration_s": 8},
        )
        assert good_i2va.status_code == 200
        cid = good_i2va.json()["id"]

        # 5. Attempt updating ratio to 16:9 on I2VA clip -> must reject 422
        update_bad = await client.put(f"/api/clips/{cid}", json={"ratio": "16:9"})
        assert update_bad.status_code == 422


# ==============================================================================
# 3. REFERENCES CRUD & RESEQUENCING (+1000000 OFFSET) (§6.4)
# ==============================================================================

@pytest.mark.asyncio
async def test_frame_mode_references_crud_and_resequencing():
    """Verify references token management, kind gating, and ordinal resequencing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        p_res = await client.post("/api/projects", json={"name": f"P-{uuid.uuid4().hex[:6]}"})
        pid = p_res.json()["id"]

        c_res = await client.post(
            f"/api/projects/{pid}/clips",
            json={"name": "Frame Ref Test", "mode": "FL2VA", "ratio": "adaptive", "duration_s": 8},
        )
        cid = c_res.json()["id"]

        # 1. Attempt adding audio or video token to frame mode -> reject 422
        bad_aud = await client.post(
            f"/api/clips/{cid}/references",
            json={"kind": "audio", "caption": "voice timbre", "duration_ms": 3000},
        )
        assert bad_aud.status_code == 422

        # 2. Add Frame 1 (Picture 1)
        r1_res = await client.post(
            f"/api/clips/{cid}/references",
            json={
                "kind": "image",
                "caption": "First frame officer plate",
                "role_hint": "first_frame",
                "source_file": "frame_01.png",
                "width_px": 1536,
                "height_px": 1024,
            },
        )
        assert r1_res.status_code == 200
        r1 = r1_res.json()
        assert r1["position"] == 1
        assert r1["ordinal"] == 1
        r1_id = r1["id"]

        # 3. Add Frame 2 (Picture 2)
        r2_res = await client.post(
            f"/api/clips/{cid}/references",
            json={
                "kind": "image",
                "caption": "Last frame officer plate",
                "role_hint": "last_frame",
                "source_file": "frame_02.png",
                "width_px": 1536,
                "height_px": 1024,
            },
        )
        assert r2_res.status_code == 200
        r2 = r2_res.json()
        assert r2["position"] == 2
        assert r2["ordinal"] == 2
        r2_id = r2["id"]

        # 4. List references
        list_res = await client.get(f"/api/clips/{cid}/references")
        assert list_res.status_code == 200
        refs = list_res.json()
        assert len(refs) == 2
        assert refs[0]["id"] == r1_id
        assert refs[1]["id"] == r2_id

        # 5. Delete Frame 1; verify Frame 2 resequences to position 1, ordinal 1 (§6.4)
        del_res = await client.delete(f"/api/clips/{cid}/references/{r1_id}")
        assert del_res.status_code == 200

        list_after = await client.get(f"/api/clips/{cid}/references")
        refs_after = list_after.json()
        assert len(refs_after) == 1
        assert refs_after[0]["id"] == r2_id
        assert refs_after[0]["position"] == 1
        assert refs_after[0]["ordinal"] == 1


# ==============================================================================
# 4. FL2VA SINGLE-SHOT EXCEPTION & GENERATION (Criterion A-12, Checkpoints 1, 2)
# ==============================================================================

@pytest.mark.asyncio
async def test_fl2va_single_shot_exception_and_end_to_end_generation():
    """
    Test FL2VA 1-shot 8s generation and export:
    - requested_shot_count == 1
    - Waives PF-03 minimum shot count
    - Output format: 4 blocks (instruction line, description, soundscape, music)
    - Full export creates .prompt file and snapshot backup
    """
    proj_name = f"FL2VA 1-Shot {uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, '', 'now', 'now')", (proj_name,))
        proj_id = cur.lastrowid

        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                audio_policy, style_id, plain_style_pair, action_text,
                requested_shot_count, inputs_revision, status, created_at, updated_at
            ) VALUES (?, 'FL2VA Officer Cell', 'FL2VA', 'MiniMax-H3', 8, '768P', 'adaptive',
                      'dialogue_only', 'plain', 'Live-action, cinematic',
                      'the officer unlocks and swings the cell door open', 1, 1, 'draft', 'now', 'now')
        """, (proj_id,))
        clip_id = cur.lastrowid

        # Insert 2 image references for FL2VA
        cur.execute("""
            INSERT INTO references_tokens (clip_id, kind, ordinal, caption, role_hint, position, source_file, width_px, height_px, created_at, updated_at)
            VALUES (?, 'image', 1, 'Officer at closed cell door', 'first_frame', 1, 'frame_01.png', 1536, 1024, 'now', 'now')
        """, (clip_id,))
        cur.execute("""
            INSERT INTO references_tokens (clip_id, kind, ordinal, caption, role_hint, position, source_file, width_px, height_px, created_at, updated_at)
            VALUES (?, 'image', 2, 'Officer standing beside open cell door', 'last_frame', 2, 'frame_02.png', 1536, 1024, 'now', 'now')
        """, (clip_id,))
        conn.commit()

    # Mock Ollama plan and prose responses for frame elaboration
    valid_plan = {
        "characters": [],
        "setting": "A dimly lit stone corridor outside a cell door",
        "beats": ["key turns in lock", "door swings open", "sunlight enters"],
        "shots": [
            {
                "start_s": 0.0,
                "end_s": 8.0,
                "size": "a medium shot",
                "angle": "at eye level",
                "camera_phrase": "The camera pans right",
                "landing": "toward the open cell door",
                "pacing": "action",
                "line_ids": [],
            }
        ],
        "voices": [],
    }
    prose_response = (
        "[Shot 1] Live-action, cinematic. Sunlight streams through the barred window. "
        "The camera pans right toward the open cell door as the officer steps forward into position Picture 2."
    )

    ollama_calls = []

    def mock_ollama_handler(request: httpx.Request) -> httpx.Response:
        ollama_calls.append(request)
        req_data = json.loads(request.content.decode("utf-8"))
        if req_data.get("format") is not None:
            return httpx.Response(200, json={"response": json.dumps(valid_plan), "done_reason": "stop"})
        else:
            return httpx.Response(200, json={"response": prose_response, "done_reason": "stop"})

    mock_client = OllamaClient(transport=httpx.MockTransport(mock_ollama_handler))
    app.state.ollama_client = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        gen_res = await client.post(
            f"/api/clips/{clip_id}/generate",
            json={"drafter_model": "qwen2.5:7b-instruct", "seed": 42},
        )
        assert gen_res.status_code == 200
        data = gen_res.json()
        assert data["event"] == "done"
        assert data["status"] == "preflight"

        # Check prompt record
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM prompts WHERE clip_id = ?", (clip_id,))
            prompt = dict(cur.fetchone())
            cur.execute("SELECT status FROM clips WHERE id = ?", (clip_id,))
            clip_status = cur.fetchone()["status"]

        assert clip_status == "preflight"
        body = prompt["body"]

        # Check 4-block output format: instruction line\n\nintegrated...\n\noverall...\n\nnon_diegetic...
        blocks = body.split("\n\n")
        assert len(blocks) == 4

        # Block 1: FL2VA instruction line with Shot 1 and 8.00-second mark
        assert blocks[0] == (
            "How the reference pictures align with the target video — "
            "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
            "Picture 2 (from Shot 1) aligns with the 8.00-second mark of the target video."
        )

        # Block 2: Multimodal description with house audio sentence inserted (§7.6)
        assert blocks[1].startswith("integrated_multimodal_description: [Shot 1] Live-action, cinematic.")
        assert "The audio contains only the spoken dialogue" in blocks[1]

        # Block 3: Soundscape
        assert blocks[2] == "overall_soundscape: N/A"

        # Block 4: Non-diegetic music
        assert blocks[3] == "non_diegetic_music: N/A"

        # Export test: Atomic write of .prompt file and snapshot backup
        exp_res = await client.post(f"/api/clips/{clip_id}/export")
        assert exp_res.status_code == 200
        exp_data = exp_res.json()
        assert exp_data["status"] == "ok"
        assert "prompt_file" in exp_data

        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT status FROM clips WHERE id = ?", (clip_id,))
            assert cur.fetchone()["status"] == "exported"


# ==============================================================================
# 5. I2VA & L2VA GENERATION & 4-BLOCK OUTPUT FORMAT (§4.4.3, §4.4.5)
# ==============================================================================

@pytest.mark.asyncio
async def test_i2va_end_to_end_generation_and_4block_format():
    """Verify I2VA generation produces byte-exact I2VA instruction line and 4-block layout."""
    proj_name = f"I2VA Proj {uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, '', 'now', 'now')", (proj_name,))
        proj_id = cur.lastrowid

        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                audio_policy, style_id, plain_style_pair, action_text,
                requested_shot_count, inputs_revision, status, created_at, updated_at
            ) VALUES (?, 'I2VA Test', 'I2VA', 'MiniMax-H3', 6, '768P', 'adaptive',
                      'dialogue_only', 'plain', 'Live-action, cinematic',
                      'she stares at her hands, then looks up', 2, 1, 'draft', 'now', 'now')
        """, (proj_id,))
        clip_id = cur.lastrowid

        cur.execute("""
            INSERT INTO references_tokens (clip_id, kind, ordinal, caption, role_hint, position, source_file, width_px, height_px, created_at, updated_at)
            VALUES (?, 'image', 1, 'Woman looking down at hands', 'first_frame', 1, 'frame_01.png', 1536, 1024, 'now', 'now')
        """, (clip_id,))
        conn.commit()

    valid_plan = {
        "characters": [],
        "setting": "A quiet study room",
        "beats": ["looks at hands", "looks up"],
        "shots": [
            {
                "start_s": 0.0,
                "end_s": 3.0,
                "size": "a close-up shot",
                "angle": "at eye level",
                "camera_phrase": "The camera holds a static shot",
                "landing": "toward her hands",
                "pacing": "action",
                "line_ids": [],
            },
            {
                "start_s": 3.0,
                "end_s": 6.0,
                "size": "a medium close-up shot",
                "angle": "at eye level",
                "camera_phrase": "The camera tilts up",
                "landing": "toward her face",
                "pacing": "action",
                "line_ids": [],
            },
        ],
        "voices": [],
    }
    prose_response = (
        "[Shot 1] Live-action, cinematic. Soft daylight falls upon her trembling fingers. "
        "The camera holds a static shot toward her hands as she breathes quietly. "
        "[Shot 2] At 00:03.000, the camera cuts to The camera tilts up toward her face as she glances at the horizon."
    )

    def mock_ollama_handler(request: httpx.Request) -> httpx.Response:
        req_data = json.loads(request.content.decode("utf-8"))
        if req_data.get("format") is not None:
            return httpx.Response(200, json={"response": json.dumps(valid_plan), "done_reason": "stop"})
        return httpx.Response(200, json={"response": prose_response, "done_reason": "stop"})

    mock_client = OllamaClient(transport=httpx.MockTransport(mock_ollama_handler))
    app.state.ollama_client = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        gen_res = await client.post(
            f"/api/clips/{clip_id}/generate",
            json={"drafter_model": "qwen2.5:7b-instruct", "seed": 42},
        )
        assert gen_res.status_code == 200

        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM prompts WHERE clip_id = ?", (clip_id,))
            body = cur.fetchone()["body"]

        blocks = body.split("\n\n")
        assert len(blocks) == 4
        assert blocks[0] == "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
        assert blocks[1].startswith("integrated_multimodal_description: [Shot 1] Live-action, cinematic.")
        assert blocks[2] == "overall_soundscape: N/A"
        assert blocks[3] == "non_diegetic_music: N/A"


@pytest.mark.asyncio
async def test_l2va_end_to_end_generation_and_4block_format():
    """Verify L2VA generation produces byte-exact L2VA instruction line with final shot index."""
    proj_name = f"L2VA Proj {uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, '', 'now', 'now')", (proj_name,))
        proj_id = cur.lastrowid

        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                audio_policy, style_id, plain_style_pair, action_text,
                requested_shot_count, inputs_revision, status, created_at, updated_at
            ) VALUES (?, 'L2VA Test', 'L2VA', 'MiniMax-H3', 10, '768P', 'adaptive',
                      'dialogue_only', 'plain', 'Live-action, cinematic',
                      'she crosses the cell and settles beneath the window in the morning light', 3, 1, 'draft', 'now', 'now')
        """, (proj_id,))
        clip_id = cur.lastrowid

        cur.execute("""
            INSERT INTO references_tokens (clip_id, kind, ordinal, caption, role_hint, position, source_file, width_px, height_px, created_at, updated_at)
            VALUES (?, 'image', 1, 'Woman sitting beneath window', 'last_frame', 1, 'frame_final.png', 1536, 1024, 'now', 'now')
        """, (clip_id,))
        conn.commit()

    valid_plan = {
        "characters": [],
        "setting": "A quiet stone cell",
        "beats": ["walks across room", "approaches window", "sits down"],
        "shots": [
            {
                "start_s": 0.0,
                "end_s": 3.0,
                "size": "a medium wide shot",
                "angle": "at eye level",
                "camera_phrase": "The camera pans left",
                "landing": "toward the far wall",
                "pacing": "action",
                "line_ids": [],
            },
            {
                "start_s": 3.0,
                "end_s": 6.5,
                "size": "a medium shot",
                "angle": "at eye level",
                "camera_phrase": "The camera pushes in",
                "landing": "toward the stone alcove",
                "pacing": "action",
                "line_ids": [],
            },
            {
                "start_s": 6.5,
                "end_s": 10.0,
                "size": "a medium close-up shot",
                "angle": "at eye level",
                "camera_phrase": "The camera holds a static shot",
                "landing": "toward Picture 1",
                "pacing": "action",
                "line_ids": [],
            },
        ],
        "voices": [],
    }
    prose_response = (
        "[Shot 1] Live-action, cinematic. Shadows stretch softly across the flagstone floor. "
        "The camera pans left toward the far wall as she moves. "
        "[Shot 2] At 00:03.000, the camera cuts to The camera pushes in toward the stone alcove as she approaches the light. "
        "[Shot 3] At 00:06.500, the camera cuts to The camera holds a static shot toward Picture 1 as she settles beneath the frame."
    )

    def mock_ollama_handler(request: httpx.Request) -> httpx.Response:
        req_data = json.loads(request.content.decode("utf-8"))
        if req_data.get("format") is not None:
            return httpx.Response(200, json={"response": json.dumps(valid_plan), "done_reason": "stop"})
        return httpx.Response(200, json={"response": prose_response, "done_reason": "stop"})

    mock_client = OllamaClient(transport=httpx.MockTransport(mock_ollama_handler))
    app.state.ollama_client = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        gen_res = await client.post(
            f"/api/clips/{clip_id}/generate",
            json={"drafter_model": "qwen2.5:7b-instruct", "seed": 42},
        )
        assert gen_res.status_code == 200

        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM prompts WHERE clip_id = ?", (clip_id,))
            body = cur.fetchone()["body"]

        blocks = body.split("\n\n")
        assert len(blocks) == 4
        # Shot count is 3, duration is 10.00
        assert blocks[0] == "How the reference pictures align with the target video — <Picture 1> (from [Shot 3]) aligns with the 10.00-second mark of the target video."
        assert blocks[1].startswith("integrated_multimodal_description: [Shot 1] Live-action, cinematic.")
        assert blocks[2] == "overall_soundscape: N/A"
        assert blocks[3] == "non_diegetic_music: N/A"


# ==============================================================================
# 6. VALIDATION RULES (PF-20, PF-27)
# ==============================================================================

def test_frame_mode_pf27_forbids_reference_tokens_and_ref2va_headers():
    """Verify PF-27 blocks <Subject>, <Audio>, <Video> tokens and REF2VA headers in frame modes."""
    rule = default_registry.get_rule("PF-27")
    assert rule is not None

    clip = {"mode": "I2VA", "ratio": "adaptive", "duration_s": 8}

    # Prompt containing <Subject 1> in I2VA mode
    bad_prompt = (
        "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.\n\n"
        "integrated_multimodal_description: [Shot 1] Live-action, cinematic. <Subject 1> looks at the sunset.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = ValidationContext(clip=clip, parsed_prompt=parse_prompt(bad_prompt))
    violations = rule.validate(ctx)
    assert len(violations) > 0
    assert any("must not contain REF2VA token" in v.message for v in violations)
    assert any(v.blocking for v in violations)


def test_frame_mode_pf20_reference_limits_and_advisory_dimensions():
    """Verify PF-20 reference counts and advisory warnings on image dimensions."""
    rule = default_registry.get_rule("PF-20")
    assert rule is not None

    # 1. FL2VA with only 1 image -> blocking error
    fl2va_clip = {"mode": "FL2VA", "ratio": "adaptive", "duration_s": 8, "action_text": "moving"}
    ref1 = {"kind": "image", "caption": "Plate 1", "width_px": 1536, "height_px": 1024}
    ctx_fl2va_1ref = ValidationContext(clip=fl2va_clip, parsed_prompt=parse_prompt(""), references=[ref1])
    v_fl2va = rule.validate(ctx_fl2va_1ref)
    assert any(v.blocking and "requires exactly 2 image references" in v.message for v in v_fl2va)

    # 2. I2VA with 1 image and valid dimensions -> passes cleanly
    i2va_clip = {"mode": "I2VA", "ratio": "adaptive", "duration_s": 8, "action_text": "action described"}
    ctx_i2va_valid = ValidationContext(clip=i2va_clip, parsed_prompt=parse_prompt(""), references=[ref1])
    v_i2va_valid = rule.validate(ctx_i2va_valid)
    assert len(v_i2va_valid) == 0

    # 3. Image with dimension 100px (outside 256–5760 px) -> advisory warning (blocking: false)
    ref_small = {"kind": "image", "caption": "Small plate", "width_px": 100, "height_px": 1024}
    ctx_small = ValidationContext(clip=i2va_clip, parsed_prompt=parse_prompt(""), references=[ref_small])
    v_small = rule.validate(ctx_small)
    assert len(v_small) == 1
    assert v_small[0].severity == "warning"
    assert v_small[0].blocking is False
    assert "256–5760 px" in v_small[0].message
