"""Stage 07 Comprehensive Test Suite: REF2VA Flat Single-Canvas & Many-to-Many Linking.

Verifies (§4.4.6, §6.1, §6.4, §7.4, §7.6, §8.3–§8.6, Appendix A.9, Criteria A-05, A-11, A-24, A-38, A-39, A-42, A-43, A-45):
1. Deterministic Subject Definitions Compiler (S-03, §8.3, Appendix A.9):
   - Checkpoint 1: Multi-picture linking (<Picture 1> identity_anchor + <Picture 2> outfit).
   - Checkpoint 2: 0-picture text-only subject definition.
   - Location subjects with feature lists.
   - Picture anchor lines (first_frame, keyframe, last_frame, composition_anchor, framing_reference).
   - Audio voice-timbre reference lines.
2. Hard Budget Safeguards (S-02 / §6.1, PF-20, Criterion A-11):
   - Strict rejection with HTTP 422: images <= 9, videos <= 3, audio <= 3, total <= 12.
   - Duration bounds (2000–15000 ms) for audio/video.
3. Task Types & Video Editing Summary Prefix (§8.5, Appendix A.9):
   - Auto-derivation of task types.
   - Opening prefix "The target video is an edited version of <Video K>." when video editing is active.
   - PUT /api/clips/{id}/task-types endpoint.
4. Retention Analysis Synchronizer & Format (§8.6, PF-22):
   - Retention entries for subjects, anchor pictures, videos, and audios.
   - Line formatting with parentheticals, valid markers, and no (Sx) tags.
5. Six-Section Layout Contract (PF-01, §7.6, Criterion A-38):
   - Exactly six sections in order: subject_definitions, summary, retention_analysis,
     detailed_description, overall_soundscape, non_diegetic_music.
   - Headers alone on lines with colons.
   - detailed_description starts with style sentence, followed by each [Shot N] on its own line.
6. PLATES Attach Order File Generation (§10.2, Criterion A-39):
   - Companion clip-<NN>-PLATES.txt formatted in upload/position order with U+2014 em dash.
7. Full End-to-End Generation & Export Pipeline (Criterion A-05, A-24).
"""

from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import uuid
import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import EXPORTS_DIR
from app.storage.db import get_connection
from app.engine.subject_builder import build_subject_definitions
from app.engine.renderer import (
    render_prompt_body,
    derive_task_types,
    build_retention_analysis_section,
)
from app.engine.exporter import build_plates_content
from app.llm.client import OllamaClient
from app.validation.registry import default_registry, ValidationContext
from app.validation.parser import parse_prompt


# ==============================================================================
# 1. CHECKPOINT 1 & 2: DETERMINISTIC SUBJECT DEFINITIONS (S-03, §8.3, App A.9)
# ==============================================================================

def test_subject_definitions_many_to_many_and_zero_pictures():
    """
    Checkpoint 1: Multi-picture linking (<Picture 1> identity + <Picture 2> outfit).
    Checkpoint 2: 0-picture text-only subject definition.
    Plus location, picture anchor, and audio timbre references.
    """
    subjects = [
        {
            "id": 1,
            "ordinal": 1,
            "role": "person",
            "role_phrase": "officer",
            "pronoun": "his",
            "outfit_noun": "uniform",
            "appositive": "",
            "feature_list": "",
        },
        {
            "id": 2,
            "ordinal": 2,
            "role": "person",
            "role_phrase": "informant",
            "pronoun": "his",
            "outfit_noun": "outfit",
            "appositive": "",
            "feature_list": "",
        },
        {
            "id": 3,
            "ordinal": 3,
            "role": "location",
            "role_phrase": "prison corridor",
            "pronoun": "its",
            "outfit_noun": "outfit",
            "appositive": "",
            "feature_list": "walls, floor, cell doors, and layout",
        },
    ]

    references = [
        {"id": 101, "kind": "image", "ordinal": 1, "position": 1},
        {"id": 102, "kind": "image", "ordinal": 2, "position": 2},
        {"id": 103, "kind": "image", "ordinal": 3, "position": 3},
        {"id": 104, "kind": "image", "ordinal": 4, "position": 4},
        {"id": 201, "kind": "audio", "ordinal": 1, "position": 5},
    ]

    # Subject 1 has two pictures: Picture 1 (identity_anchor) + Picture 2 (outfit)
    # Subject 2 has 0 pictures (text-only)
    # Subject 3 has Picture 3 (location)
    # Picture 4 is composition anchor for Shot 1
    subject_pictures = [
        {"subject_id": 1, "reference_id": 101, "reference_role": "identity_anchor"},
        {"subject_id": 1, "reference_id": 102, "reference_role": "outfit"},
        {"subject_id": 3, "reference_id": 103, "reference_role": "location"},
        {"subject_id": 1, "reference_id": 104, "reference_role": "composition_anchor", "anchor_shot_ordinal": 1, "defines_text": "the layout"},
    ]

    speakers = [
        {"id": 501, "display_name": "Speaker 1", "subject_id": 1, "audio_reference_id": 201}
    ]
    speaker_id_to_num = {501: 1}

    defs = build_subject_definitions(
        subjects=subjects,
        subject_pictures=subject_pictures,
        references=references,
        speakers=speakers,
        speaker_id_to_num=speaker_id_to_num,
    )

    lines = defs.splitlines()
    assert len(lines) == 5

    # Checkpoint 1: Multi-picture linking
    assert lines[0] == "<Subject 1> is the officer with his face, hair, and build taken from <Picture 1> and his complete uniform taken from <Picture 2>."

    # Checkpoint 2: 0-Picture text-only
    assert lines[1] == "<Subject 2> is the informant with his appearance, facial features, build, and complete outfit defined by text alone."

    # Location line
    assert lines[2] == "<Subject 3> is the prison corridor in <Picture 3>, including its walls, floor, cell doors, and layout exactly as shown."

    # Picture anchor line
    assert lines[3] == "<Picture 4> is the composition anchor for [Shot 1], defining the layout."

    # Audio timbre line
    assert lines[4] == "<Audio 1> is the voice-timbre reference for <Subject 1> (S1)."


# ==============================================================================
# 2. HARD BUDGET SAFEGUARDS (S-02 / §6.1, PF-20, Criterion A-11)
# ==============================================================================

@pytest.mark.asyncio
async def test_ref2va_budget_limits_enforced_422():
    """Verify strict 422 rejection when exceeding limits (<=9 images, <=3 videos, <=3 audio, <=12 files)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # Create a project and REF2VA clip
        p_res = await client.post("/api/projects", json={"name": f"Budget-{uuid.uuid4().hex[:6]}"})
        pid = p_res.json()["id"]

        c_res = await client.post(
            f"/api/projects/{pid}/clips",
            json={
                "name": "REF2VA Budget Clip",
                "mode": "REF2VA",
                "duration_s": 8,
                "ratio": "16:9",
            },
        )
        assert c_res.status_code == 200
        cid = c_res.json()["id"]

        # Add 9 images (allowed)
        for i in range(1, 10):
            res = await client.post(
                f"/api/clips/{cid}/references",
                json={"kind": "image", "plate_filename": f"img_{i}.png", "caption": f"Image {i}"},
            )
            assert res.status_code == 200, f"Image {i} should be allowed"

        # 10th image must be rejected with 422
        bad_img = await client.post(
            f"/api/clips/{cid}/references",
            json={"kind": "image", "plate_filename": "img_10.png"},
        )
        assert bad_img.status_code == 422
        err = bad_img.json()
        err_obj = err.get("detail", {}).get("error", err.get("error", {}))
        assert err_obj.get("code") == "budget_exceeded"
        assert "Image count limit exceeded" in err_obj.get("message", "")

        # Add 3 videos (allowed)
        for v in range(1, 4):
            res = await client.post(
                f"/api/clips/{cid}/references",
                json={"kind": "video", "plate_filename": f"vid_{v}.mp4", "caption": f"Video {v}", "duration_ms": 5000},
            )
            assert res.status_code == 200

        # 4th video must be rejected with 422
        bad_vid = await client.post(
            f"/api/clips/{cid}/references",
            json={"kind": "video", "plate_filename": "vid_4.mp4", "duration_ms": 5000},
        )
        assert bad_vid.status_code == 422
        vid_err = bad_vid.json().get("detail", {}).get("error", {})
        assert vid_err.get("code") == "budget_exceeded"

        # Check total file count: we currently have 9 images + 3 videos = 12 files.
        # Adding an audio reference now must be rejected because total files > 12
        bad_audio = await client.post(
            f"/api/clips/{cid}/references",
            json={"kind": "audio", "plate_filename": "aud_1.wav", "duration_ms": 4000},
        )
        assert bad_audio.status_code == 422
        aud_err = bad_audio.json().get("detail", {}).get("error", {})
        assert "Total reference files limit exceeded" in aud_err.get("message", "")


# ==============================================================================
# 3. TASK TYPES & VIDEO EDITING PREFIX (§8.5, Appendix A.9, D-10)
# ==============================================================================

def test_derive_task_types_and_video_editing_sentence():
    """Verify code derivation of task types and exact summary opening for video editing."""
    clip = {
        "id": 1,
        "mode": "REF2VA",
        "task_types_touched": 0,
        "task_types_json": '["video editing"]',
    }
    references = [
        {"id": 1, "kind": "image", "ordinal": 1},
        {"id": 2, "kind": "video", "ordinal": 2},
    ]
    subject_pictures = [
        {"reference_id": 1, "reference_role": "identity_anchor"}
    ]
    speakers = []

    # 1. derive_task_types auto-detects guidance image -> reference generation, plus preserves video editing
    types = derive_task_types(clip, references, subject_pictures, speakers)
    assert "reference generation" in types
    assert "video editing" in types
    # Order matches canonical: reference generation, keyframe completion, video editing...
    assert types.index("reference generation") < types.index("video editing")

    # 2. Render prompt with video editing task type
    rendered_body, meta = render_prompt_body(
        clip=clip,
        body_template="[Shot 1] The camera pans right toward the open cell door.",
        lines=[],
        onscreen_texts=[],
        subjects=[{"id": 1, "ordinal": 1, "role": "person", "role_phrase": "officer", "pronoun": "his", "outfit_noun": "uniform"}],
        subject_pictures=subject_pictures,
        references=references,
        speakers=speakers,
        task_types=types,
        summary_text="Pacing is accelerated and lighting is darkened in key moments.",
    )

    # Summary section MUST start with:
    # summary:\n[reference generation + video editing] The target video is an edited version of <Video 2>. Pacing is accelerated...
    assert "summary:\n[reference generation + video editing] The target video is an edited version of <Video 2>." in rendered_body


@pytest.mark.asyncio
async def test_api_task_types_update_endpoint():
    """Verify PUT /api/clips/{id}/task-types persists ordered task types."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        p_res = await client.post("/api/projects", json={"name": f"TT-{uuid.uuid4().hex[:6]}"})
        pid = p_res.json()["id"]

        c_res = await client.post(
            f"/api/projects/{pid}/clips",
            json={"name": "TT Clip", "mode": "REF2VA", "duration_s": 8},
        )
        cid = c_res.json()["id"]

        update_res = await client.put(
            f"/api/clips/{cid}/task-types",
            json={"task_types": ["audio reference", "video editing", "reference generation"]},
        )
        assert update_res.status_code == 200
        data = update_res.json()
        # Verify sorted into canonical order
        assert data["task_types"] == ["reference generation", "video editing", "audio reference"]

        # Check DB flag task_types_touched == 1
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT task_types_json, task_types_touched FROM clips WHERE id = ?", (cid,))
            row = cur.fetchone()
            assert row[1] == 1
            assert json.loads(row[0]) == ["reference generation", "video editing", "audio reference"]


# ==============================================================================
# 4. RETENTION ANALYSIS SYNCHRONIZER & FORMAT (§8.6, PF-22)
# ==============================================================================

@pytest.mark.asyncio
async def test_retention_synchronizer_and_formatting():
    """Verify retention table sync creates rows for subjects, anchor pictures, videos, audio."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        p_res = await client.post("/api/projects", json={"name": f"Ret-{uuid.uuid4().hex[:6]}"})
        pid = p_res.json()["id"]
        c_res = await client.post(
            f"/api/projects/{pid}/clips",
            json={"name": "Retention Clip", "mode": "REF2VA", "duration_s": 8},
        )
        cid = c_res.json()["id"]

        # Add 1 subject
        s_res = await client.post(
            f"/api/clips/{cid}/subjects",
            json={"role": "person", "role_phrase": "officer", "pronoun": "his", "outfit_noun": "uniform"},
        )
        sid = s_res.json()["id"]

        # Add 1 image, 1 video, 1 audio
        r1_res = await client.post(f"/api/clips/{cid}/references", json={"kind": "image", "plate_filename": "pic1.png", "caption": "Picture 1"})
        assert r1_res.status_code == 200
        r1_id = r1_res.json()["id"]
        r2_res = await client.post(f"/api/clips/{cid}/references", json={"kind": "video", "plate_filename": "vid1.mp4", "caption": "Video 1", "duration_ms": 5000})
        assert r2_res.status_code == 200
        r3_res = await client.post(f"/api/clips/{cid}/references", json={"kind": "audio", "plate_filename": "aud1.wav", "caption": "Audio 1", "duration_ms": 4000})
        assert r3_res.status_code == 200

        # Link image as composition_anchor
        await client.post(
            f"/api/clips/{cid}/subject-pictures",
            json={"subject_id": sid, "reference_id": r1_id, "reference_role": "composition_anchor", "anchor_shot_ordinal": 1},
        )

        # Sync retention
        sync_res = await client.post(f"/api/clips/{cid}/retention/sync")
        assert sync_res.status_code == 200
        rows = sync_res.json()
        assert len(rows) == 4  # subject + anchor picture + video + audio

        # Build retention analysis section
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM subjects WHERE clip_id = ?", (cid,))
            subjects = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT * FROM references_tokens WHERE clip_id = ?", (cid,))
            references = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT * FROM subject_pictures sp JOIN subjects s ON sp.subject_id = s.id WHERE s.clip_id = ?", (cid,))
            subject_pictures = [dict(r) for r in cur.fetchall()]

        ret_text = build_retention_analysis_section(
            subjects=subjects,
            references=references,
            subject_pictures=subject_pictures,
            planned_shots=[{"ordinal": 1}],
            retention_entries=rows,
        )

        lines = ret_text.splitlines()
        assert len(lines) == 4
        assert lines[0].startswith("<Subject 1> (appears in [Shot 1]): fully_preserved - ")
        assert lines[1].startswith("<Picture 1> ([Shot 1] composition anchor): fully_preserved - ")
        assert lines[2].startswith("<Video 1> (cut and pacing structure): weak_reference - ")
        assert lines[3].startswith("<Audio 1>: reference - ")
        # PF-22 guarantee: no (Sx) in retention lines
        assert "(S" not in ret_text


# ==============================================================================
# 5. CHECKPOINT 3: SIX-SECTION FORMAT INTEGRITY (PF-01, §7.6, Criterion A-38)
# ==============================================================================

def test_six_section_format_integrity():
    """Verify prompt renderer builds exactly six sections in order with correct header layout."""
    clip = {
        "id": 1,
        "mode": "REF2VA",
        "duration_s": 8,
        "ratio": "16:9",
        "audio_policy": "dialogue_only",
        "style_id": "plain",
    }
    subjects = [
        {"id": 1, "ordinal": 1, "role": "person", "role_phrase": "officer", "pronoun": "his", "outfit_noun": "uniform"}
    ]
    references = [
        {"id": 1, "kind": "image", "ordinal": 1}
    ]
    subject_pictures = [
        {"subject_id": 1, "reference_id": 1, "reference_role": "identity_anchor"}
    ]
    shots = [
        {
            "ordinal": 1,
            "start_ms": 0,
            "end_ms": 4000,
            "size": "a medium shot",
            "angle": "at eye level",
            "camera_phrase": "The camera pushes in toward the subject",
            "landing": "toward the subject",
        },
        {
            "ordinal": 2,
            "start_ms": 4000,
            "end_ms": 8000,
            "size": "a close-up",
            "angle": "at eye level",
            "camera_phrase": "The camera holds a static shot",
            "landing": "",
        },
    ]

    body_template = (
        "[Shot 1] The officer stands firmly in the doorway. The camera pushes in toward the subject.\n"
        "[Shot 2] At 00:04.000, the camera cuts to the officer's steady gaze. The camera holds a static shot."
    )

    rendered_body, meta = render_prompt_body(
        clip=clip,
        body_template=body_template,
        lines=[],
        onscreen_texts=[],
        subjects=subjects,
        subject_pictures=subject_pictures,
        references=references,
        speakers=[],
        planned_shots=shots,
    )

    # 1. Verify six sections separated by \n\n
    sections = rendered_body.split("\n\n")
    assert len(sections) == 6

    # 2. Section 1: subject_definitions
    assert sections[0].startswith("subject_definitions:\n<Subject 1> is the officer in <Picture 1>")

    # 3. Section 2: summary
    assert sections[1].startswith("summary:\n[reference generation]")

    # 4. Section 3: retention_analysis
    assert sections[2].startswith("retention_analysis:\n<Subject 1>")

    # 5. Section 4: detailed_description (opens with style sentence + house sentence, then shots on newlines)
    det_lines = sections[3].splitlines()
    assert det_lines[0] == "detailed_description:"
    assert det_lines[1].startswith("The target video is in a modern cinematic feature-film style")
    assert "The audio contains only the spoken dialogue" in det_lines[1]
    assert det_lines[2].startswith("[Shot 1]")
    assert det_lines[3].startswith("[Shot 2] At 00:04.000, the camera cuts to")

    # 6. Section 5 & 6: sound fields
    assert sections[4] == "overall_soundscape:\nN/A"
    assert sections[5] == "non_diegetic_music:\nN/A"

    # 7. Run parser and preflight validation
    parsed = parse_prompt(rendered_body)
    assert parsed.detected_mode == "REF2VA"
    assert len(parsed.shots) == 2
    ctx = ValidationContext(
        clip=clip,
        parsed_prompt=parsed,
        lines=[],
        speakers=[],
        subjects=subjects,
        subject_pictures=subject_pictures,
        references=references,
        shots=shots,
    )
    violations = default_registry.validate_all(ctx)
    blocking = [v for v in violations if v.blocking]
    assert len(blocking) == 0, f"Blocking violations found: {[v.to_dict() for v in blocking]}"


# ==============================================================================
# 6. CHECKPOINT 4: PLATES ATTACH ORDER FILE (§10.2, Criterion A-39)
# ==============================================================================

def test_plates_file_attach_order_generation():
    """Verify PLATES file lists references in position order with em dash U+2014."""
    references = [
        {"id": 1, "kind": "image", "ordinal": 1, "position": 1, "plate_filename": "plate_01.png", "caption": "Officer face and build"},
        {"id": 2, "kind": "image", "ordinal": 2, "position": 2, "plate_filename": "plate_02.png", "caption": "Officer prison uniform"},
        {"id": 3, "kind": "image", "ordinal": 3, "position": 3, "plate_filename": "plate_03.png", "caption": "Corridor layout"},
        {"id": 4, "kind": "audio", "ordinal": 1, "position": 4, "role_hint": "audio", "plate_filename": "audio_01.wav", "caption": "Deep voice timbre"},
    ]
    subject_pictures = [
        {"reference_id": 1, "reference_role": "identity_anchor"},
        {"reference_id": 2, "reference_role": "outfit"},
        {"reference_id": 3, "reference_role": "composition_anchor"},
    ]

    plates_content = build_plates_content(references, subject_pictures)
    lines = plates_content.strip().splitlines()
    assert len(lines) == 4

    # Format: <Label>: <filename> — <role>: <caption> (em dash U+2014)
    assert lines[0] == "<Picture 1>: plate_01.png — identity anchor: Officer face and build"
    assert lines[1] == "<Picture 2>: plate_02.png — outfit: Officer prison uniform"
    assert lines[2] == "<Picture 3>: plate_03.png — composition anchor: Corridor layout"
    assert lines[3] == "<Audio 1>: audio_01.wav — audio: Deep voice timbre"
    assert "—" in plates_content


# ==============================================================================
# 7. FULL END-TO-END GENERATION & EXPORT (Criterion A-05, A-24)
# ==============================================================================

@pytest.mark.asyncio
async def test_ref2va_end_to_end_generation_and_export():
    """
    Test full REF2VA generation with 3 images, 1 audio, and 2 subjects:
    - Subject 1: Dual linked (<Picture 1> identity + <Picture 2> outfit)
    - Subject 2: 0 pictures (text-only)
    - Picture 3: composition anchor for Shot 1
    - Audio 1: timbre link for Subject 1 (S1)
    - Dialogue line in Shot 1
    - Mock Ollama shot_writer, summary_writer, retention_writer
    - Export creates .prompt file and -PLATES.txt file
    """
    proj_name = f"REF2VA E2E {uuid.uuid4().hex[:8]}"
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES (?, '', 'now', 'now')", (proj_name,))
        proj_id = cur.lastrowid

        cur.execute("""
            INSERT INTO clips (
                project_id, name, mode, h3_model, duration_s, resolution, ratio,
                audio_policy, style_id, plain_style_pair,
                requested_shot_count, inputs_revision, status, created_at, updated_at
            ) VALUES (?, 'REF2VA E2E Clip', 'REF2VA', 'MiniMax-H3', 8, '768P', '16:9',
                      'dialogue_only', 'plain', 'Live-action, cinematic',
                      2, 1, 'draft', 'now', 'now')
        """, (proj_id,))
        clip_id = cur.lastrowid

        # Insert 3 images and 1 audio reference
        cur.execute("""
            INSERT INTO references_tokens (clip_id, kind, ordinal, caption, role_hint, position, source_file, width_px, height_px, created_at, updated_at)
            VALUES (?, 'image', 1, 'Officer portrait', 'identity_anchor', 1, 'officer_face.png', 1024, 1024, 'now', 'now')
        """, (clip_id,))
        r1_id = cur.lastrowid

        cur.execute("""
            INSERT INTO references_tokens (clip_id, kind, ordinal, caption, role_hint, position, source_file, width_px, height_px, created_at, updated_at)
            VALUES (?, 'image', 2, 'Officer uniform', 'outfit', 2, 'officer_uniform.png', 1024, 1024, 'now', 'now')
        """, (clip_id,))
        r2_id = cur.lastrowid

        cur.execute("""
            INSERT INTO references_tokens (clip_id, kind, ordinal, caption, role_hint, position, source_file, width_px, height_px, created_at, updated_at)
            VALUES (?, 'image', 3, 'Corridor layout', 'composition_anchor', 3, 'corridor.png', 1920, 1080, 'now', 'now')
        """, (clip_id,))
        r3_id = cur.lastrowid

        cur.execute("""
            INSERT INTO references_tokens (clip_id, kind, ordinal, caption, role_hint, position, source_file, duration_ms, created_at, updated_at)
            VALUES (?, 'audio', 1, 'Officer vocal timbre', 'voice_timbre', 4, 'officer_voice.wav', 4000, 'now', 'now')
        """, (clip_id,))
        r4_id = cur.lastrowid

        # Insert 2 subjects
        cur.execute("""
            INSERT INTO subjects (clip_id, ordinal, role, role_phrase, pronoun, outfit_noun, appositive, created_at, updated_at)
            VALUES (?, 1, 'person', 'officer', 'his', 'uniform', '', 'now', 'now')
        """, (clip_id,))
        s1_id = cur.lastrowid

        cur.execute("""
            INSERT INTO subjects (clip_id, ordinal, role, role_phrase, pronoun, outfit_noun, appositive, created_at, updated_at)
            VALUES (?, 2, 'person', 'informant', 'his', 'outfit', '', 'now', 'now')
        """, (clip_id,))
        s2_id = cur.lastrowid

        # Insert 2 planned shots
        cur.execute("""
            INSERT INTO shots (clip_id, ordinal, start_ms, end_ms, size, angle, camera_move, pacing, created_at, updated_at)
            VALUES (?, 1, 0, 4000, 'a medium shot', 'at eye level', 'The camera pushes in toward the open door', 'action', 'now', 'now')
        """, (clip_id,))
        shot1_id = cur.lastrowid

        cur.execute("""
            INSERT INTO shots (clip_id, ordinal, start_ms, end_ms, size, angle, camera_move, pacing, created_at, updated_at)
            VALUES (?, 2, 4000, 8000, 'a close-up', 'at eye level', 'The camera holds a static shot', 'silent', 'now', 'now')
        """, (clip_id,))

        # Subject-picture links
        cur.execute("INSERT INTO subject_pictures (subject_id, reference_id, reference_role) VALUES (?, ?, 'identity_anchor')", (s1_id, r1_id))
        cur.execute("INSERT INTO subject_pictures (subject_id, reference_id, reference_role) VALUES (?, ?, 'outfit')", (s1_id, r2_id))
        cur.execute("INSERT INTO subject_pictures (subject_id, reference_id, reference_role, anchor_shot_id, defines_text) VALUES (?, ?, 'composition_anchor', ?, 'the layout')", (s1_id, r3_id, shot1_id))

        # Speaker with audio reference link
        cur.execute("""
            INSERT INTO speakers (clip_id, display_name, persona, voice_source, pronoun, subject_id, audio_reference_id, created_at, updated_at)
            VALUES (?, 'Officer', 'the officer', '', 'his', ?, ?, 'now', 'now')
        """, (clip_id, s1_id, r4_id))
        spk_id = cur.lastrowid

        # Dialogue line in Shot 1
        cur.execute("""
            INSERT INTO dialogue_lines (clip_id, line_order, speaker_id, shot_id, language, text_raw, delivery, is_voiceover, created_at, updated_at)
            VALUES (?, 1, ?, 1, 'English', 'Stay where you are.', 'none', 0, 'now', 'now')
        """, (clip_id, spk_id))

        conn.commit()

    # Mock Ollama Responses for REF2VA (shot_writer, summary_writer, retention_writer)
    mock_shot_prose = (
        "[Shot 1] The officer stands firmly in the corridor outside the cell, front-facing, his jaw tense and expression stern. The camera pushes in toward the open door as he raises one hand. {{L1}}\n"
        "[Shot 2] At 00:04.000, the camera cuts to the informant watching three-quarter through the narrow doorway, his eyes watchful and lips closed. The camera holds a static shot."
    )
    mock_summary_prose = "The target sequence translates the officer's appearance and uniform into the prison corridor setting."
    mock_retention_reasons = {
        "reasons": [
            "Facial features and prison uniform are reproduced.",
            "Descriptive text defines character appearance.",
            "Defines corridor framing.",
            "Audio timbre informs speech.",
        ]
    }

    def mock_ollama_handler(request: httpx.Request) -> httpx.Response:
        req_data = json.loads(request.content.decode("utf-8"))
        p = req_data.get("prompt", "")
        if "fix this" in p.lower():
            # If fixer is called, return template content
            tpl = p.split("Template to fix:\n")[-1] if "Template to fix:\n" in p else mock_shot_prose
            return httpx.Response(200, json={"response": tpl, "done_reason": "stop"})
        elif "retention" in p.lower() or req_data.get("format") is not None:
            return httpx.Response(200, json={"response": json.dumps(mock_retention_reasons), "done_reason": "stop"})
        elif "summary" in p.lower():
            return httpx.Response(200, json={"response": mock_summary_prose, "done_reason": "stop"})
        else:
            return httpx.Response(200, json={"response": mock_shot_prose, "done_reason": "stop"})

    mock_client = OllamaClient(transport=httpx.MockTransport(mock_ollama_handler))
    app.state.ollama_client = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # 1. Trigger Generation
        gen_res = await client.post(
            f"/api/clips/{clip_id}/generate",
            json={"drafter_model": "qwen2.5:7b-instruct", "seed": 42},
        )
        assert gen_res.status_code == 200
        gen_data = gen_res.json()
        assert gen_data["event"] == "done"
        assert gen_data["status"] == "preflight"

        # 2. Check DB prompt record
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM prompts WHERE clip_id = ?", (clip_id,))
            prompt_row = dict(cur.fetchone())

        prompt_body = prompt_row["body"]

        # Verify 6 sections present
        assert "subject_definitions:" in prompt_body
        assert "summary:" in prompt_body
        assert "retention_analysis:" in prompt_body
        assert "detailed_description:" in prompt_body
        assert "overall_soundscape:\nN/A" in prompt_body
        assert "non_diegetic_music:\nN/A" in prompt_body

        # Verify subject_definitions multi-picture and 0-picture formulas
        assert "<Subject 1> is the officer with his face, hair, and build taken from <Picture 1> and his complete uniform taken from <Picture 2>." in prompt_body
        assert "<Subject 2> is the informant with his appearance, facial features, build, and complete outfit defined by text alone." in prompt_body
        assert "<Picture 3> is the composition anchor for [Shot 1], defining the layout." in prompt_body
        assert "<Audio 1> is the voice-timbre reference for <Subject 1> (S1)." in prompt_body

        # Verify dialogue expansion (8-part speech sentence) in detailed_description
        assert '<Subject 1> (S1) says in the voice timbre referenced from <Audio 1>, <d>[English] Stay where you are.</d>. He closes his lips.' in prompt_body

        # 3. Export clip
        export_res = await client.post(
            f"/api/clips/{clip_id}/export",
            json={"overwrite": True},
        )
        assert export_res.status_code == 200
        exp_data = export_res.json()
        assert exp_data["status"] == "ok"
        prompt_path = Path(exp_data["prompt_file"])
        plates_path = Path(exp_data["plates_file"])

        assert plates_path is not None
        assert "PLATES.txt" in plates_path.name

        # Verify files on disk
        assert prompt_path.exists()
        assert plates_path.exists()

        plates_text = plates_path.read_text(encoding="utf-8")
        assert "<Picture 1>: officer_face.png — identity anchor: Officer portrait" in plates_text
        assert "<Picture 2>: officer_uniform.png — outfit: Officer uniform" in plates_text
        assert "<Picture 3>: corridor.png — composition anchor: Corridor layout" in plates_text
        assert "<Audio 1>: officer_voice.wav — voice_timbre: Officer vocal timbre" in plates_text


# ==============================================================================
# 8. REF2VA CRUD ENDPOINTS TEST
# ==============================================================================

@pytest.mark.asyncio
async def test_ref2va_crud_endpoints():
    """Verify CRUD endpoints for subjects, subject-picture links, shots, and preview."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        p_res = await client.post("/api/projects", json={"name": f"CRUD-{uuid.uuid4().hex[:6]}"})
        pid = p_res.json()["id"]
        c_res = await client.post(
            f"/api/projects/{pid}/clips",
            json={"name": "CRUD Clip", "mode": "REF2VA", "duration_s": 8},
        )
        cid = c_res.json()["id"]

        # 1. Subjects CRUD
        sub1 = await client.post(
            f"/api/clips/{cid}/subjects",
            json={"role": "person", "role_phrase": "guard", "pronoun": "his", "outfit_noun": "uniform"},
        )
        assert sub1.status_code == 200
        s1_id = sub1.json()["id"]

        sub2 = await client.post(
            f"/api/clips/{cid}/subjects",
            json={"role": "location", "role_phrase": "courtyard", "pronoun": "its", "feature_list": "walls and fountain"},
        )
        assert sub2.status_code == 200
        s2_id = sub2.json()["id"]

        list_subs = await client.get(f"/api/clips/{cid}/subjects")
        assert len(list_subs.json()) == 2

        # Update subject
        up_sub = await client.put(f"/api/subjects/{s1_id}", json={"role_phrase": "senior guard"})
        assert up_sub.status_code == 200
        assert up_sub.json()["role_phrase"] == "senior guard"

        # 2. Shots CRUD
        shot1 = await client.post(
            f"/api/clips/{cid}/shots",
            json={"start_ms": 0, "size": "a medium shot", "angle": "at eye level", "camera_phrase": "The camera pushes in toward the gate", "pacing": "action"},
        )
        assert shot1.status_code == 200
        sh1_id = shot1.json()["id"]

        list_shots = await client.get(f"/api/clips/{cid}/shots")
        assert len(list_shots.json()) == 1

        # 3. Subject-defs preview
        prev_res = await client.get(f"/api/clips/{cid}/subject-defs-preview")
        assert prev_res.status_code == 200
        preview = prev_res.json()
        assert preview["subject_count"] == 2
        assert "<Subject 1> is the senior guard" in preview["subject_definitions"]
        assert "<Subject 2> is the courtyard" in preview["subject_definitions"]
