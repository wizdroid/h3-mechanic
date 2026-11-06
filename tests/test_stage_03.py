"""Stage 03 Comprehensive Test Suite.

Verifies:
- Golden Instruction Lines (I2VA, FL2VA, L2VA)
- Placeholder Protocol & Template Integrity Checker (§8.0)
- Deterministic Subject Definitions Builder (S-03)
- Canonical 8-Part Speech Sentence Expansion & Lip Closure (§8.0)
- Cross-Cut Destination Prefix Placement after Cut Header (S-04)
- Fallback Prose Stitcher preserving all placeholders (S-05)
- Atomic Exporter with Integer NN Collision Detection (S-07)
- PLATES file generator with U+2014 em dashes (§10.2)
- JSON Snapshot Backup and Pruning to 5 per clip (§10.1)
- Export API Routes: preview and export
"""

from __future__ import annotations
import json
import os
from pathlib import Path
import sqlite3
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.resources.vocab import HOUSE_SENTENCE
from app.engine.placeholders import (
    build_placeholder_maps,
    validate_template_integrity,
)
from app.engine.subject_builder import build_subject_definitions
from app.engine.renderer import (
    build_instruction_line,
    expand_speech_sentence,
    expand_onscreen_text,
    apply_cross_cut_destination_prefixes,
    stitch_fallback_prose,
    render_prompt_body,
)
from app.engine.exporter import (
    check_collision,
    suggest_next_clip_number,
    write_atomic_file,
    build_plates_content,
    create_json_snapshot,
    prune_snapshots,
    export_clip,
    ExportCollisionError,
    PreflightBlockedError,
)
from app.storage.db import get_db_connection

# ============================================================================
# 1. GOLDEN INSTRUCTION LINE TESTS
# ============================================================================

def test_golden_instruction_lines():
    # 1. I2VA
    i2va_line = build_instruction_line("I2VA", shot_count=1, duration_s=5)
    assert i2va_line == "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."

    # 2. FL2VA with 2 shots, 8s duration:
    # Exact: "How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 2) aligns with the 8.00-second mark of the target video."
    # Em dash U+2014, no angle or square brackets around Picture or Shot
    fl2va_line = build_instruction_line("FL2VA", shot_count=2, duration_s=8)
    expected_fl2va = (
        "How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
        "Picture 2 (from Shot 2) aligns with the 8.00-second mark of the target video."
    )
    assert fl2va_line == expected_fl2va
    assert "—" in fl2va_line  # U+2014 em dash
    assert "<" not in fl2va_line and "[" not in fl2va_line

    # 3. L2VA with 3 shots, 10s duration:
    # Exact: "How the reference pictures align with the target video — <Picture 1> (from [Shot 3]) aligns with the 10.00-second mark of the target video."
    l2va_line = build_instruction_line("L2VA", shot_count=3, duration_s=10)
    expected_l2va = "How the reference pictures align with the target video — <Picture 1> (from [Shot 3]) aligns with the 10.00-second mark of the target video."
    assert l2va_line == expected_l2va
    assert "<Picture 1>" in l2va_line
    assert "[Shot 3]" in l2va_line

# ============================================================================
# 2. PLACEHOLDER PROTOCOL & TEMPLATE INTEGRITY TESTS
# ============================================================================

def test_placeholder_protocol_ordering():
    lines = [
        {"id": 20, "shot_start_ms": 3000, "line_order": 1},
        {"id": 10, "shot_start_ms": 0, "line_order": 1},
        {"id": 15, "shot_start_ms": 0, "line_order": 2},
    ]
    onscreen = [{"id": 1, "ordinal": 1}, {"id": 2, "ordinal": 2}]

    l_map, stub_to_line, t_map, stub_to_t = build_placeholder_maps(lines, onscreen)

    # Line 10 (start 0, order 1) -> {{L1}}
    assert l_map[10] == "{{L1}}"
    # Line 15 (start 0, order 2) -> {{L2}}
    assert l_map[15] == "{{L2}}"
    # Line 20 (start 3000, order 1) -> {{L3}}
    assert l_map[20] == "{{L3}}"

    assert t_map[1] == "{{T1}}"
    assert t_map[2] == "{{T2}}"

def test_template_integrity_validation():
    # 1. Valid template
    template_ok = "[Shot 1] The camera pushes in. {{L1}} {{T1}} [Shot 2] At 00:03.000, the camera cuts to {{L2}}."
    errs = validate_template_integrity(
        template_ok,
        mode="T2VA",
        expected_line_stubs=["{{L1}}", "{{L2}}"],
        expected_tm_stubs=["{{T1}}"],
    )
    assert len(errs) == 0

    # 2. Sequence strictly increasing violation (L2 before L1)
    template_reversed = "[Shot 1] The camera pushes in. {{L2}} [Shot 2] At 00:03.000, the camera cuts to {{L1}}."
    errs_rev = validate_template_integrity(
        template_reversed,
        mode="T2VA",
        expected_line_stubs=["{{L1}}", "{{L2}}"],
        expected_tm_stubs=[],
    )
    assert any("strictly increasing" in e for e in errs_rev)

    # 3. Missing placeholder
    template_missing = "[Shot 1] The camera pushes in. {{L1}}."
    errs_miss = validate_template_integrity(
        template_missing,
        mode="T2VA",
        expected_line_stubs=["{{L1}}", "{{L2}}"],
        expected_tm_stubs=[],
    )
    assert any("Missing required dialogue placeholder '{{L2}}'" in e for e in errs_miss)

    # 4. Duplicate placeholder
    template_dup = "[Shot 1] The camera pushes in. {{L1}} {{L1}}."
    errs_dup = validate_template_integrity(
        template_dup,
        mode="T2VA",
        expected_line_stubs=["{{L1}}"],
        expected_tm_stubs=[],
    )
    assert any("Duplicate dialogue placeholder" in e for e in errs_dup)

    # 5. Forbidden {{V: token
    template_v = "[Shot 1] {{V:F3}} {{L1}}."
    errs_v = validate_template_integrity(
        template_v,
        mode="T2VA",
        expected_line_stubs=["{{L1}}"],
        expected_tm_stubs=[],
    )
    assert any("forbidden placeholder prefix '{{V:'" in e for e in errs_v)

    # 6. REF2VA shot ownership check
    ref_template = (
        "[Shot 1] The camera holds a static shot. {{L2}}\n"
        "[Shot 2] At 00:03.000, the camera cuts to The camera pushes in. {{L1}}\n"
    )
    errs_ref = validate_template_integrity(
        ref_template,
        mode="REF2VA",
        expected_line_stubs=["{{L1}}", "{{L2}}"],
        expected_tm_stubs=[],
        line_to_shot_ordinal={"{{L1}}": 1, "{{L2}}": 2},
    )
    assert any("belongs to [Shot 1]" in e for e in errs_ref)

# ============================================================================
# 3. DETERMINISTIC SUBJECT DEFINITIONS (S-03)
# ============================================================================

def test_subject_definitions_zero_pictures():
    """Person with 0 pictures linked (pure descriptive text)."""
    subjects = [
        {
            "id": 1,
            "ordinal": 1,
            "role": "person",
            "role_phrase": "police commissioner",
            "appositive": "a stern veteran officer",
            "pronoun": "his",
            "outfit_noun": "khaki uniform",
        }
    ]
    defs = build_subject_definitions(subjects, subject_pictures=[], references=[])
    expected = (
        "<Subject 1> is the police commissioner, a stern veteran officer, "
        "with his appearance, facial features, build, and complete khaki uniform defined by text alone."
    )
    assert defs == expected

def test_subject_definitions_one_picture():
    """Person with 1 picture linked (identity anchor)."""
    subjects = [
        {
            "id": 1,
            "ordinal": 1,
            "role": "person",
            "role_phrase": "investigative journalist",
            "pronoun": "her",
            "outfit_noun": "trench coat",
        }
    ]
    refs = [{"id": 10, "ordinal": 1, "kind": "image"}]
    subject_pictures = [
        {"subject_id": 1, "reference_id": 10, "reference_role": "identity_anchor"}
    ]
    defs = build_subject_definitions(subjects, subject_pictures, refs)
    expected = (
        "<Subject 1> is the investigative journalist in <Picture 1> "
        "with her face, hair, build, and complete trench coat taken exactly from the reference."
    )
    assert defs == expected

def test_subject_definitions_multiple_pictures():
    """Person with multiple pictures linked: Picture 1 (identity anchor) and Picture 2 (outfit)."""
    subjects = [
        {
            "id": 1,
            "ordinal": 1,
            "role": "person",
            "role_phrase": "secret agent",
            "appositive": "operating undercover",
            "pronoun": "his",
            "outfit_noun": "tactical gear",
        }
    ]
    refs = [
        {"id": 10, "ordinal": 1, "kind": "image"},
        {"id": 20, "ordinal": 2, "kind": "image"},
    ]
    subject_pictures = [
        {"subject_id": 1, "reference_id": 10, "reference_role": "identity_anchor"},
        {"subject_id": 1, "reference_id": 20, "reference_role": "outfit"},
    ]
    defs = build_subject_definitions(subjects, subject_pictures, refs)
    expected = (
        "<Subject 1> is the secret agent with his face, hair, and build taken from <Picture 1>, "
        "operating undercover, and his complete tactical gear taken from <Picture 2>."
    )
    assert defs == expected

def test_subject_definitions_anchors_and_audio():
    """Picture anchors and voice-timbre audio lines ordering."""
    subjects = [
        {
            "id": 1,
            "ordinal": 1,
            "role": "person",
            "role_phrase": "detective",
            "pronoun": "her",
            "outfit_noun": "suit",
        }
    ]
    refs = [
        {"id": 10, "ordinal": 1, "kind": "image"},
        {"id": 30, "ordinal": 1, "kind": "audio"},
    ]
    subject_pictures = [
        {"subject_id": 1, "reference_id": 10, "reference_role": "identity_anchor"},
        {"subject_id": 1, "reference_id": 10, "reference_role": "first_frame", "anchor_shot_ordinal": 1, "defines_text": "the layout"},
    ]
    speakers = [
        {"id": 100, "subject_id": 1, "audio_reference_id": 30}
    ]
    spk_map = {100: 1}

    defs = build_subject_definitions(subjects, subject_pictures, refs, speakers, spk_map)
    lines = defs.splitlines()

    assert len(lines) == 3
    # 1. Subject definition
    assert lines[0].startswith("<Subject 1> is the detective in <Picture 1>")
    # 2. Picture anchor line
    assert lines[1] == "<Picture 1> is the first frame for [Shot 1], defining the layout."
    # 3. Audio voice timbre line
    assert lines[2] == "<Audio 1> is the voice-timbre reference for <Subject 1> (S1)."

# ============================================================================
# 4. CANONICAL 8-PART SPEECH EXPANSION TESTS
# ============================================================================

def test_expand_speech_sentence_kannada_dialogue():
    """Verify Kannada dialogue line with delivery manner, accent, and lip closure."""
    line = {
        "id": 1,
        "speaker_id": 10,
        "language": "Kannada",
        "text_raw": "ಸತ್ಯ ಹೇಳು।",  # Should be normalized to dot
        "delivery": "interrogation",  # verb: "asks sharply", manner: "each question clipped"
        "is_voiceover": 0,
        "crosses_cut": 0,
        "cutoff": 0,
    }
    speakers = {
        10: {
            "id": 10,
            "display_name": "Rao",
            "persona": "police inspector",
            "voice_id": "M5",  # "in a hard, clipped mid-low male voice with a brisk staccato pace"
            "accent": "speaking Kannada with a natural Bengaluru urban accent",
            "pronoun": "his",
        }
    }
    speaker_map = {10: 1}

    sentence = expand_speech_sentence(
        line=line,
        mode="T2VA",
        speaker_id_to_num=speaker_map,
        speakers_by_id=speakers,
        subjects_by_id={},
        references_by_id={},
    )

    # 1. Speaker ref: The police inspector
    assert sentence.startswith("The police inspector (S1)")
    # 2. Verb: asks sharply
    assert "asks sharply" in sentence
    # 3. Voice phrase: M5 paste phrase
    assert "in a hard, clipped mid-low male voice with a brisk staccato pace" in sentence
    # 4. Accent clause
    assert ", speaking Kannada with a natural Bengaluru urban accent" in sentence
    # 5. Delivery manner
    assert ", each question clipped" in sentence
    # 6. Dialogue: native script with dot
    assert "<d>[Kannada] ಸತ್ಯ ಹೇಳು.</d>" in sentence
    # 7. Lip closure: He closes his lips.
    assert sentence.endswith("He closes his lips.")

def test_expand_speech_sentence_voiceover():
    """Voiceover lip closure: 'while {pronoun} lips remain completely closed.'"""
    line = {
        "id": 2,
        "speaker_id": 20,
        "language": "English",
        "text_raw": "I knew what was coming.",
        "delivery": "whisper",  # verb replaced by voiceover verb, manner preserved
        "is_voiceover": 1,
        "crosses_cut": 0,
        "cutoff": 0,
    }
    speakers = {
        20: {
            "id": 20,
            "display_name": "Maya",
            "persona": "young woman",
            "voice_id": "F1",
            "pronoun": "her",
        }
    }
    sentence = expand_speech_sentence(
        line=line,
        mode="T2VA",
        speaker_id_to_num={20: 1},
        speakers_by_id=speakers,
        subjects_by_id={},
        references_by_id={},
    )

    assert "says in an off-screen voiceover" in sentence
    assert "barely audible" in sentence
    assert "<d>[English] I knew what was coming.</d>" in sentence
    assert sentence.endswith("while her lips remain completely closed.")

# ============================================================================
# 5. CROSS-CUT DESTINATION PLACEMENT (S-04)
# ============================================================================

def test_cross_cut_destination_placement():
    """
    S-04 Safeguard:
    For destination shot N > 1, place prefix immediately AFTER the cut header:
    [Shot 2] At 00:03.500, the camera cuts to <scenetrans> The audio continues seamlessly across the cut.
    """
    prompt_text = (
        "[Shot 1] The detective speaks <scenetrans> <d>[English] Look behind you!</d> "
        "[Shot 2] At 00:03.500, the camera cuts to The camera pushes in toward the dark shadow."
    )
    result = apply_cross_cut_destination_prefixes(prompt_text, cross_cut_dest_shot_numbers={2})

    expected_shot2_start = "[Shot 2] At 00:03.500, the camera cuts to <scenetrans> The audio continues seamlessly across the cut. "
    assert expected_shot2_start in result
    # Check that cut header timestamp is intact at start of shot 2
    assert "[Shot 2] At 00:03.500, the camera cuts to <scenetrans>" in result

# ============================================================================
# 6. FALLBACK PROSE STITCHER (S-05)
# ============================================================================

def test_fallback_prose_preserves_all_placeholders():
    """
    S-05 Safeguard: Stitches structured plan shots while guaranteeing that ALL
    {{Lk}} and {{Tm}} placeholders for each shot are preserved without loss.
    """
    clip = {
        "style_id": "plain",
        "plain_style_pair": "Live-action, cinematic",
    }
    planned_shots = [
        {
            "ordinal": 1,
            "start_ms": 0,
            "size": "a medium close-up",
            "angle": "at eye level",
            "events": "the officer leans over the desk",
            "camera_phrase": "The camera pushes in",
            "landing": "toward the papers",
        },
        {
            "ordinal": 2,
            "start_ms": 3000,
            "size": "a close-up",
            "angle": "front-facing",
            "events": "the suspect turns pale",
            "camera_phrase": "The camera holds a static shot",
            "landing": "revealing his expression",
        },
    ]
    line_stubs = {1: ["{{L1}}"], 2: ["{{L2}}"]}
    tm_stubs = {1: ["{{T1}}"], 2: []}

    prose = stitch_fallback_prose(clip, planned_shots, line_stubs, tm_stubs)

    assert "[Shot 1] Live-action, cinematic," in prose
    assert "{{L1}}" in prose
    assert "{{T1}}" in prose
    assert "[Shot 2] At 00:03.000, the camera cuts to" in prose
    assert "{{L2}}" in prose

# ============================================================================
# 7. ATOMIC EXPORTER & INTEGER NN COLLISION (S-07)
# ============================================================================

def test_integer_nn_collision_detection(tmp_path):
    """
    S-07 Safeguard: Collision detection MUST be decided on integer NN alone!
    Both clip-1-8s.txt and clip-01-8s.txt collide.
    """
    # Create existing file clip-01-8s.txt in tmp_path
    existing_file = tmp_path / "clip-01-8s.txt"
    existing_file.write_text("existing prompt", encoding="utf-8")

    # Attempt collision check with NN = 1
    colliding = check_collision(1, export_dir=tmp_path)
    assert len(colliding) == 1
    assert colliding[0] == "clip-01-8s.txt"

    # Attempt collision check with padded NN = 01
    colliding_padded = check_collision("01", export_dir=tmp_path)
    assert len(colliding_padded) == 1

    # Suggest next clip number must return 2
    next_nn = suggest_next_clip_number(export_dir=tmp_path)
    assert next_nn == 2

    # Collision check with NN = 2 must have NO collision
    assert len(check_collision(2, export_dir=tmp_path)) == 0

def test_atomic_file_write_guarantee(tmp_path):
    """Verify atomic write using temp file + os.link/replace."""
    target = tmp_path / "clip-02-5s.txt"
    content = "Hello prompt\n"

    # 1. Normal write
    write_atomic_file(target, content, overwrite=False)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == content

    # 2. Overwrite=False when target exists raises FileExistsError
    with pytest.raises(FileExistsError):
        write_atomic_file(target, "New content", overwrite=False)

    # 3. Overwrite=True atomically replaces
    new_content = "Replaced prompt\n"
    write_atomic_file(target, new_content, overwrite=True)
    assert target.read_text(encoding="utf-8") == new_content

def test_plates_file_formatting():
    """Verify PLATES file generation with U+2014 em dashes and ordered roles."""
    refs = [
        {"id": 1, "ordinal": 1, "kind": "image", "source_file": "hero.jpg", "caption": "Lead protagonist in leather jacket", "position": 1},
        {"id": 2, "ordinal": 1, "kind": "audio", "source_file": "", "caption": "Voice timbre reference", "position": 2},
    ]
    sub_pics = [
        {"reference_id": 1, "reference_role": "identity_anchor"},
        {"reference_id": 1, "reference_role": "first_frame"},
    ]
    plates_text = build_plates_content(refs, sub_pics)
    lines = plates_text.strip().splitlines()

    assert len(lines) == 2
    # Image line
    assert lines[0] == "<Picture 1>: hero.jpg — identity anchor, first frame: Lead protagonist in leather jacket"
    # Audio line with empty filename -> MISSING
    assert lines[1] == "<Audio 1>: MISSING — unassigned: Voice timbre reference"
    assert "—" in lines[0]  # em dash

def test_snapshot_backup_and_pruning(tmp_path):
    """Verify JSON snapshot is written and pruned to last 5 per clip."""
    clip_id = 99
    # Create 7 snapshots
    for i in range(1, 8):
        ts = f"2026110612000{i}"
        snap_file = tmp_path / f"clip-{clip_id}-{ts}.json"
        snap_file.write_text(f'{{"index": {i}}}', encoding="utf-8")

    # Prune
    prune_snapshots(clip_id, backup_dir=tmp_path, keep_last=5)

    remaining = sorted(list(tmp_path.glob(f"clip-{clip_id}-*.json")))
    assert len(remaining) == 5
    # The oldest 2 (index 1 and 2) must have been deleted
    assert not (tmp_path / f"clip-{clip_id}-20261106120001.json").exists()
    assert not (tmp_path / f"clip-{clip_id}-20261106120002.json").exists()
    # The newest 5 remain
    assert (tmp_path / f"clip-{clip_id}-20261106120007.json").exists()

# ============================================================================
# 8. API EXPORT ROUTES & COLLISION HTTP 409
# ============================================================================

@pytest.mark.asyncio
async def test_api_export_endpoints(tmp_path):
    """Test /api/clips/{id}/export-preview and /api/clips/{id}/export."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM projects WHERE name = 'Export Test Project'")
    cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES ('Export Test Project', '', 'now', 'now')")
    proj_id = cur.lastrowid

    cur.execute("""
        INSERT INTO clips (
            project_id, name, mode, h3_model, duration_s, resolution, ratio,
            audio_policy, style_id, plain_style_pair, inputs_revision, created_at, updated_at
        ) VALUES (?, 'Export Clip', 'T2VA', 'MiniMax-H3', 5, '768P', '16:9', 'dialogue_only', 'plain', 'Live-action, cinematic', 1, 'now', 'now')
    """, (proj_id,))
    clip_id = cur.lastrowid

    test_prompt = (
        f"integrated_multimodal_description: [Shot 1] Live-action, cinematic. {HOUSE_SENTENCE} "
        "The camera pushes in toward the window.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )

    cur.execute("""
        INSERT INTO prompts (
            clip_id, generation_id, stage, inputs_revision, body_template,
            body, char_count, overrides_json, created_at
        ) VALUES (?, 'gen-export-1', 'draft', 1, ?, ?, ?, '[]', 'now')
    """, (clip_id, test_prompt, test_prompt, len(test_prompt)))

    conn.commit()
    conn.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # 1. GET export preview
        resp_prev = await client.get(f"/api/clips/{clip_id}/export-preview")
        assert resp_prev.status_code == 200
        prev_data = resp_prev.json()
        assert "suggested_clip_number" in prev_data
        assert "prompt_filename" in prev_data

        # 2. POST export (Success)
        resp_export = await client.post(
            f"/api/clips/{clip_id}/export",
            json={"clip_number": 88, "overwrite": True},
        )
        assert resp_export.status_code == 200
        res_data = resp_export.json()
        assert res_data["status"] == "ok"
        assert "clip-88-5s.txt" in res_data["prompt_file"]

        # 3. POST export with same NN without overwrite -> HTTP 409 Collision!
        resp_collision = await client.post(
            f"/api/clips/{clip_id}/export",
            json={"clip_number": 88, "overwrite": False},
        )
        assert resp_collision.status_code == 409
        err = resp_collision.json()["detail"]["error"]
        assert err["code"] == "collision"
        assert err["clip_number"] == 88

        # Clean up exported test file
        target_file = Path(res_data["prompt_file"])
        target_file.unlink(missing_ok=True)
