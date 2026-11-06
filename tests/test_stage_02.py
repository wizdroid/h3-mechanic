"""Stage 02 Comprehensive Test Suite.

Verifies:
- Vocabularies and resource loaders
- Estimators (§9.5) and text normalizers
- Parser (§9.6)
- Preflight rules PF-01 through PF-35 (§9.1, §9.2)
- Deterministic 5-step autofix engine (§9.6, S-06)
- Overrides mechanics (§9.4)
- API endpoints: validate-inputs, preflight, override, and vocab
"""

from __future__ import annotations
import json
import sqlite3
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.resources.vocab import (
    get_camera_moves,
    get_mood_words,
    get_sound_lexicon,
    get_scripts,
    get_voices,
    HOUSE_SENTENCE,
)
from app.validation.estimators import (
    count_english_words,
    count_indic_syllables,
    estimate_speech_tenths,
    estimate_line_duration_tenths,
    estimate_shot_min_duration_ms,
    assign_speaker_numbers,
    normalize_text_raw,
    format_ms_timestamp,
    count_sentences,
)
from app.validation.parser import parse_prompt, ParsedPrompt
from app.validation.registry import default_registry, ValidationContext, Violation
from app.validation.autofix import run_deterministic_autofix
from app.storage.db import get_db_connection

# ============================================================================
# 1. ESTIMATOR & RESOURCE TESTS
# ============================================================================

def test_vocab_loaders():
    cam = get_camera_moves()
    assert "camera_patterns" in cam
    assert "The camera holds a static shot" in cam["camera_patterns"]

    moods = get_mood_words()
    assert "tense" in moods["errors"]
    assert "sad" in moods["errors"]
    assert "peaceful" in moods["warnings"]

    sound_lex = get_sound_lexicon()
    assert "footstep" in sound_lex
    assert "drone" in sound_lex

    scripts = get_scripts()
    assert "Kannada" in scripts
    assert "Hindi" in scripts

    voices = get_voices()
    assert "F1" in voices
    assert "M1" in voices
    assert "K1" in voices

def test_estimators_worked_example():
    """Verify §9.5 worked example: 5 English words -> 20 tenths, 25 tenths line, 3500ms min shot."""
    text = "This is a simple sentence."
    words = count_english_words(text)
    assert words == 5

    speech_tenths = estimate_speech_tenths(text, "English")
    assert speech_tenths == 20  # 5 * 4

    line_tenths = estimate_line_duration_tenths(text, "English")
    assert line_tenths == 25  # 20 + 5

    shot_min = estimate_shot_min_duration_ms([{"text_raw": text, "language": "English"}])
    assert shot_min == 3500  # (10 + 25) * 100

def test_indic_syllable_counter():
    # Kannada: ಒಳಗೆ ಹೋಗು. (o-la-ge ho-gu)
    # Characters: ಒ(Lo), ಳ(Lo), ಗ(Lo)+ೆ(Mn), ಹ(Lo)+ೋ(Mc), ಗ(Lo)+ು(Mn) -> 5 consonants/independent vowels
    kannada_text = "ಒಳಗೆ ಹೋಗು."
    syl = count_indic_syllables(kannada_text, "Kannada")
    assert syl > 0

    # Virama suppression check: Devanagari 'स्त' (स + ् + त): त is preceded by virama, so only स is counted as onset
    hindi_text = "सच बताओ."
    syl_hi = count_indic_syllables(hindi_text, "Hindi")
    assert syl_hi >= 3

def test_normalize_text_raw():
    assert normalize_text_raw("Hello world") == "Hello world."
    assert normalize_text_raw("Hello world.  ") == "Hello world."
    assert normalize_text_raw("क्या हाल है।") == "क्या हाल है."
    assert normalize_text_raw("सत्य बोल॥") == "सत्य बोल."
    assert normalize_text_raw("Are you sure?") == "Are you sure?"
    assert normalize_text_raw("Stop!") == "Stop!"

def test_assign_speaker_numbers():
    lines = [
        {"id": 101, "shot_start_ms": 0, "line_order": 1, "speaker_id": 42},
        {"id": 102, "shot_start_ms": 0, "line_order": 2, "speaker_id": 99},
        {"id": 103, "shot_start_ms": 3000, "line_order": 1, "speaker_id": 42},
        {"id": 104, "shot_start_ms": 3000, "line_order": 2, "speaker_id": 15},
    ]
    mapping = assign_speaker_numbers(lines)
    assert mapping[42] == 1
    assert mapping[99] == 2
    assert mapping[15] == 3

def test_sentence_counter():
    assert count_sentences("One sentence.") == 1
    assert count_sentences("First sentence. Second sentence! Third sentence?") == 3
    # Exclude abbreviations like Dr. and Mr.
    assert count_sentences("Dr. Smith went to the hospital.") == 1
    # Exclude decimal digits
    assert count_sentences("The score was 3.14 points. That is high.") == 2

# ============================================================================
# 2. PARSER & AUTOFIX TESTS
# ============================================================================

def test_parser_t2va():
    body = (
        "integrated_multimodal_description: [Shot 1] Live-action, cinematic, "
        f"{HOUSE_SENTENCE} The camera pushes in toward the window.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    parsed = parse_prompt(body)
    assert parsed.detected_mode == "T2VA"
    assert "integrated_multimodal_description" in parsed.sections
    assert len(parsed.shots) == 1
    assert parsed.shots[0].camera_family == "push"
    assert parsed.shots[0].landing == "toward"

def test_parser_ref2va():
    body = (
        "subject_definitions:\n"
        "<Subject 1> is the detective in <Picture 1>, with his face, hair, build, and complete outfit taken exactly from the reference.\n\n"
        "summary:\n"
        "[reference generation] A gritty neo-noir sequence.\n\n"
        "retention_analysis:\n"
        "<Subject 1> (appears in [Shot 1]): fully_preserved - key character.\n\n"
        "detailed_description:\n"
        f"The target video is in a neo-noir crime-thriller style. {HOUSE_SENTENCE}\n"
        "[Shot 1] The camera holds a static shot revealing the dimly lit alley.\n"
        "[Shot 2] At 00:03.000, the camera cuts to The camera pushes in toward <Subject 1>.\n\n"
        "overall_soundscape:\n"
        "N/A\n\n"
        "non_diegetic_music:\n"
        "N/A"
    )
    parsed = parse_prompt(body)
    assert parsed.detected_mode == "REF2VA"
    assert len(parsed.sections) == 6
    assert len(parsed.shots) == 2
    assert parsed.shots[0].number == 1
    assert parsed.shots[1].start_ms == 3000

def test_autofix_all_five_passes():
    raw_prompt = (
        "integrated_multimodal_description: [Shot 1] Live-action, cinematic. "
        "The detective says: <d>[English] Stop right there!</d> "
        "[Shot 2] At 00:03:000, the shot cuts to the camera pushes in toward the desk.\n\n"
        "overall_soundscape: Some city ambience.\n\n"
        "non_diegetic_music: Gentle piano melody."
    )
    # Under dialogue_only:
    # Pass 1: At 00:03:000 -> At 00:03.000
    # Pass 2: the shot cuts to -> the camera cuts to
    # Pass 3: the camera pushes in -> The camera pushes in
    # Pass 4: says: <d> -> says, <d>
    # Pass 5: soundscape & music -> N/A, house sentence inserted
    fixed = run_deterministic_autofix(raw_prompt, audio_policy="dialogue_only", mode="T2VA")

    assert "At 00:03.000, the camera cuts to" in fixed
    assert "The camera pushes in" in fixed
    assert "says, <d>" in fixed
    assert "overall_soundscape: N/A" in fixed
    assert "non_diegetic_music: N/A" in fixed
    assert HOUSE_SENTENCE in fixed

def test_autofix_ref2va_multiline_sound_fields():
    raw_ref = (
        "subject_definitions:\n<Subject 1> is the lead.\n\n"
        "summary:\n[reference generation] Scene.\n\n"
        "retention_analysis:\n<Subject 1>: fully_preserved - key.\n\n"
        "detailed_description:\nThe target video is cinematic.\n[Shot 1] The camera holds a static shot.\n\n"
        "overall_soundscape:\nHeavy rain and thunder outside.\n\n"
        "non_diegetic_music:\nPulsing synth baseline."
    )
    fixed = run_deterministic_autofix(raw_ref, audio_policy="dialogue_only", mode="REF2VA")
    assert "overall_soundscape:\nN/A" in fixed
    assert "non_diegetic_music:\nN/A" in fixed
    assert HOUSE_SENTENCE in fixed

# ============================================================================
# 3. PREFLIGHT RULES PF-01 THROUGH PF-35 TESTS
# ============================================================================

def make_test_context(
    body: str,
    mode: str = "T2VA",
    audio_policy: str = "dialogue_only",
    duration_s: int = 5,
    ratio: str = "16:9",
    video_model: str = "MiniMax-H3",
    resolution: str = "768P",
    lines: list = None,
    references: list = None,
    speakers: list = None,
    subjects: list = None,
    shots: list = None,
    overrides: dict = None,
    inputs_revision: int = 1,
) -> ValidationContext:
    clip = {
        "id": 1,
        "mode": mode,
        "audio_policy": audio_policy,
        "duration_s": duration_s,
        "ratio": ratio,
        "video_model": video_model,
        "resolution": resolution,
        "inputs_revision": inputs_revision,
    }
    prompt = {
        "id": 1,
        "clip_id": 1,
        "body": body,
        "inputs_revision": inputs_revision,
        "overrides_json": "[]",
    }
    parsed = parse_prompt(body)
    return ValidationContext(
        clip=clip,
        parsed_prompt=parsed,
        prompt=prompt,
        lines=lines or [],
        references=references or [],
        speakers=speakers or [],
        subjects=subjects or [],
        shots=shots or [],
        overrides=overrides or {},
    )

def test_pf01_template_integrity():
    rule = default_registry.get_rule("PF-01")
    # Failing: Carriage return and trailing spaces
    bad_body = "integrated_multimodal_description: [Shot 1] Hello \r\n\noverall_soundscape: N/A\n\nnon_diegetic_music: N/A "
    ctx = make_test_context(bad_body)
    violations = rule.validate(ctx)
    assert any(v.rule_id == "PF-01" for v in violations)

def test_pf02_shot_timestamps():
    rule = default_registry.get_rule("PF-02")
    # Shot 1 has timestamp -> Error
    body = (
        "integrated_multimodal_description: [Shot 1] At 00:00.000, the camera cuts to The camera holds a static shot.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body)
    violations = rule.validate(ctx)
    assert any("must not have a timestamp" in v.message for v in violations)

    # Shot cuts to -> Warning
    body_warn = (
        "integrated_multimodal_description: [Shot 1] The camera holds a static shot. "
        "[Shot 2] At 00:02.000, the shot cuts to The camera pushes in toward the door.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx_warn = make_test_context(body_warn)
    v_warn = rule.validate(ctx_warn)
    assert any(v.severity == "warning" for v in v_warn)

def test_pf03_shot_budgets():
    rule = default_registry.get_rule("PF-03")
    # 4s clip with 3 shots (allowed 1-2 shots)
    body = (
        "integrated_multimodal_description: [Shot 1] The camera holds a static shot. "
        "[Shot 2] At 00:01.000, the camera cuts to The camera pushes in toward the door. "
        "[Shot 3] At 00:02.500, the camera cuts to The camera pulls out revealing the street.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body, duration_s=4)
    violations = rule.validate(ctx)
    assert any("outside allowed range" in v.message for v in violations)

def test_pf04_camera_phrases_and_modifiers():
    rule = default_registry.get_rule("PF-04")
    # Illegal modifier on static shot
    body = (
        "integrated_multimodal_description: [Shot 1] The camera holds a static shot at slow speed.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body)
    violations = rule.validate(ctx)
    assert any("forbids all speed and amplitude modifiers" in v.message for v in violations)

    # Missing landing on push
    body_no_landing = (
        "integrated_multimodal_description: [Shot 1] The camera pushes in into the darkness.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx2 = make_test_context(body_no_landing)
    violations2 = rule.validate(ctx2)
    assert any("needs a landing substring" in v.message for v in violations2)

def test_pf05_face_heuristic():
    rule = default_registry.get_rule("PF-05")
    # Close up with face, missing front-facing/three-quarter and expression token
    body = (
        "integrated_multimodal_description: [Shot 1] A close-up of the woman. "
        "The camera pushes in toward her.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body)
    violations = rule.validate(ctx)
    assert any("must be 'front-facing' or 'three-quarter'" in v.message for v in violations)

def test_pf06_speech_expansion():
    rule = default_registry.get_rule("PF-06")
    # Contains bare library ID F3
    body = (
        "integrated_multimodal_description: [Shot 1] The detective speaks in F3: <d>[English] Stop!</d> "
        "The camera pushes in toward him.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body)
    violations = rule.validate(ctx)
    assert any("bare voice library ID 'F3'" in v.message for v in violations)

def test_pf07_dialogue_punctuation():
    rule = default_registry.get_rule("PF-07")
    # Dialogue ends with Indic danda
    body = (
        "integrated_multimodal_description: [Shot 1] The officer speaks <d>[Hindi] अंदर जाओ।</d> "
        "The camera pushes in toward him.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body)
    violations = rule.validate(ctx)
    assert any("ends with illegal Indic danda" in v.message for v in violations)

def test_pf08_sound_fields():
    rule = default_registry.get_rule("PF-08")
    # Dialogue only policy, but soundscape has prose
    body = (
        "integrated_multimodal_description: [Shot 1] The camera holds a static shot.\n\n"
        "overall_soundscape: Rain pattering on the roof.\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body, audio_policy="dialogue_only")
    violations = rule.validate(ctx)
    assert any("overall_soundscape must be exactly 'N/A'" in v.message for v in violations)

def test_pf08b_mood_words():
    rule = default_registry.get_rule("PF-08b")
    # non_diegetic_music contains tense (error) and joyful (warning)
    body = (
        "integrated_multimodal_description: [Shot 1] The camera holds a static shot.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: A tense string section with joyful flute."
    )
    ctx = make_test_context(body, audio_policy="custom")
    violations = rule.validate(ctx)
    assert any(v.severity == "error" and "tense" in v.message for v in violations)
    assert any(v.severity == "warning" and "joyful" in v.message for v in violations)

def test_pf09_char_limit_and_fences():
    rule = default_registry.get_rule("PF-09")
    # Contains markdown fences
    body = (
        "```text\n"
        "integrated_multimodal_description: [Shot 1] The camera holds a static shot.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A\n"
        "```"
    )
    ctx = make_test_context(body)
    violations = rule.validate(ctx)
    assert any("Markdown code fences" in v.message for v in violations)

def test_pf10_english_prose():
    rule = default_registry.get_rule("PF-10")
    # Indic script outside <d>
    body = (
        "integrated_multimodal_description: [Shot 1] The detective says नमस्ते. "
        "The camera pushes in toward him.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body)
    violations = rule.validate(ctx)
    assert any("All prompt fields must be English" in v.message for v in violations)

def test_pf11_ratio_concrete():
    rule = default_registry.get_rule("PF-11")
    # T2VA with adaptive ratio -> Error
    ctx = make_test_context("body", mode="T2VA", ratio="adaptive")
    violations = rule.validate(ctx)
    assert any("T2VA requires a concrete ratio" in v.message for v in violations)

    # I2VA with 16:9 ratio -> Error (must be adaptive)
    ctx_i2va = make_test_context("body", mode="I2VA", ratio="16:9")
    violations_i2va = rule.validate(ctx_i2va)
    assert any("requires 'adaptive' ratio" in v.message for v in violations_i2va)

def test_pf12_shot_partition():
    rule = default_registry.get_rule("PF-12")
    # Last shot has < 12 words -> Warning
    body = (
        "integrated_multimodal_description: [Shot 1] Live-action, cinematic. "
        "The camera holds a static shot revealing the harbor at dawn. "
        "[Shot 2] At 00:03.000, the camera cuts to The camera pushes in toward the boat.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body, duration_s=5)
    violations = rule.validate(ctx)
    assert any(v.severity == "warning" and "fewer than 12 words" in v.message for v in violations)

def test_pf13_video_model_matrix():
    rule = default_registry.get_rule("PF-13")
    # MiniMax-H3 duration 3s (< 4s) -> Error
    ctx = make_test_context("body", video_model="MiniMax-H3", duration_s=3)
    violations = rule.validate(ctx)
    assert any("MiniMax-H3 allows integer durations 4–15 seconds" in v.message for v in violations)

    # MiniMax-H3-Max with 2K resolution -> Error
    ctx2 = make_test_context("body", video_model="MiniMax-H3-Max", duration_s=6, resolution="2K")
    violations2 = rule.validate(ctx2)
    assert any("MiniMax-H3-Max allows resolutions '480P' or '768P'" in v.message for v in violations2)

def test_pf20_reference_limits_and_advisory_dimensions():
    rule = default_registry.get_rule("PF-20")
    # 10 images (> 9)
    refs = [{"kind": "image", "ordinal": i} for i in range(1, 11)]
    # Plus one image with 100x100 dimensions (outside 256-5760 px) -> Advisory warning (non-blocking)
    refs[0]["width_px"] = 100
    refs[0]["height_px"] = 100

    ctx = make_test_context("body", mode="REF2VA", references=refs)
    violations = rule.validate(ctx)

    # Check hard error for count
    assert any(v.rule_id == "PF-20" and v.blocking and "budget exceeded" in v.message for v in violations)
    # Check advisory warning for dimensions
    advisory = [v for v in violations if "dimensions" in v.message]
    assert len(advisory) == 1
    assert advisory[0].severity == "warning"
    assert not advisory[0].blocking

def test_pf21_summary_task_types():
    rule = default_registry.get_rule("PF-21")
    body = (
        "subject_definitions:\n<Subject 1> is the lead.\n\n"
        "summary:\n[invalid task type] A summary.\n\n"
        "retention_analysis:\n<Subject 1>: fully_preserved - key.\n\n"
        "detailed_description:\nThe target video is cinematic.\n[Shot 1] The camera holds a static shot.\n\n"
        "overall_soundscape:\nN/A\n\n"
        "non_diegetic_music:\nN/A"
    )
    ctx = make_test_context(body, mode="REF2VA")
    violations = rule.validate(ctx)
    assert any("not an approved task type" in v.message for v in violations)

def test_pf22_retention_markers():
    rule = default_registry.get_rule("PF-22")
    body = (
        "subject_definitions:\n<Subject 1> is the lead.\n\n"
        "summary:\n[reference generation] A summary.\n\n"
        "retention_analysis:\n<Subject 1> (S1): fully_preserved - key character.\n\n"
        "detailed_description:\nThe target video is cinematic.\n[Shot 1] The camera holds a static shot.\n\n"
        "overall_soundscape:\nN/A\n\n"
        "non_diegetic_music:\nN/A"
    )
    ctx = make_test_context(body, mode="REF2VA")
    violations = rule.validate(ctx)
    assert any("must not contain speaker tags such as '(Sx)'" in v.message for v in violations)

def test_pf23_subject_definitions_formulas():
    rule = default_registry.get_rule("PF-23")
    # Missing reference row in definitions
    refs = [{"kind": "image", "ordinal": 1}]
    body = (
        "subject_definitions:\n<Subject 1> is the person defined by text alone.\n\n"
        "summary:\n[reference generation] A summary.\n\n"
        "retention_analysis:\n<Subject 1>: fully_preserved - key.\n\n"
        "detailed_description:\nThe target video is cinematic.\n[Shot 1] The camera holds a static shot.\n\n"
        "overall_soundscape:\nN/A\n\n"
        "non_diegetic_music:\nN/A"
    )
    ctx = make_test_context(body, mode="REF2VA", references=refs)
    violations = rule.validate(ctx)
    assert any("Reference row <Picture 1> does not appear" in v.message for v in violations)

def test_pf24_style_sentence():
    rule = default_registry.get_rule("PF-24")
    body = (
        "subject_definitions:\n<Subject 1> is the lead.\n\n"
        "summary:\n[reference generation] A summary.\n\n"
        "retention_analysis:\n<Subject 1>: fully_preserved - key.\n\n"
        "detailed_description:\nIn 1980s Bollywood style.\n[Shot 1] The camera holds a static shot.\n\n"
        "overall_soundscape:\nN/A\n\n"
        "non_diegetic_music:\nN/A"
    )
    ctx = make_test_context(body, mode="REF2VA")
    violations = rule.validate(ctx)
    assert any("must begin with a style sentence starting 'The target video is …'" in v.message for v in violations)

def test_pf27_token_contamination():
    rule = default_registry.get_rule("PF-27")
    # T2VA contains <Picture 1>
    body = (
        "integrated_multimodal_description: [Shot 1] The camera pushes in toward <Picture 1> revealing the wall.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body, mode="T2VA")
    violations = rule.validate(ctx)
    assert any("must not contain REF2VA token '<Picture'" in v.message for v in violations)

def test_pf28_template_integrity():
    rule = default_registry.get_rule("PF-28")
    body = (
        "integrated_multimodal_description: [Shot 1] The camera pushes in toward {{L1}} revealing the room.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body, mode="T2VA")
    violations = rule.validate(ctx)
    assert any("contains unexpanded template placeholders" in v.message for v in violations)

def test_pf30_stale_prompt():
    rule = default_registry.get_rule("PF-30")
    ctx = make_test_context("body", inputs_revision=2)
    ctx.prompt["inputs_revision"] = 1
    violations = rule.validate(ctx)
    assert any("Inputs changed since this draft" in v.message for v in violations)

def test_pf31_native_script_input():
    rule = default_registry.get_rule("PF-31")
    lines = [{"language": "Hindi", "text_raw": "andar jao"}]  # Romanized Hindi without Devanagari
    ctx = make_test_context("body", lines=lines)
    violations = rule.validate(ctx)
    assert any("must contain native script" in v.message for v in violations)

def test_pf32_onscreen_text():
    rule = default_registry.get_rule("PF-32")
    body = (
        'integrated_multimodal_description: [Shot 1] A weathered billboard reads "This Is Far Too Many Words For Text". '
        "The camera holds a static shot.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body)
    violations = rule.validate(ctx)
    assert any("exceeds 3 words" in v.message for v in violations)

def test_pf33_filler_words():
    rule = default_registry.get_rule("PF-33")
    body = (
        "integrated_multimodal_description: [Shot 1] Live-action, cinematic. Masterpiece 4k dynamic camera. "
        "The camera pushes in toward the river.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body)
    violations = rule.validate(ctx)
    assert any("generic quality filler tag" in v.message for v in violations)

def test_pf34_sound_lexicon():
    rule = default_registry.get_rule("PF-34")
    body = (
        "integrated_multimodal_description: [Shot 1] Heavy footsteps echo through the empty corridor. "
        "The camera pushes in toward the gate.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body, audio_policy="dialogue_only")
    violations = rule.validate(ctx)
    assert any("contains banned sound word 'footsteps'" in v.message for v in violations)

def test_pf35_house_audio_sentence():
    rule = default_registry.get_rule("PF-35")
    # Dialogue-only without house sentence
    body = (
        "integrated_multimodal_description: [Shot 1] Live-action, cinematic. "
        "The camera pushes in toward the desk.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    ctx = make_test_context(body, audio_policy="dialogue_only")
    violations = rule.validate(ctx)
    assert any("house sentence must occur exactly once" in v.message for v in violations)

# ============================================================================
# 4. OVERRIDE MECHANICS & API ROUTE TESTS
# ============================================================================

def test_heuristic_override_mechanics():
    """Verify that heuristic rules can be overridden with notes, suppressing blocking."""
    rule_pf04 = default_registry.get_rule("PF-04")
    body = (
        "integrated_multimodal_description: [Shot 1] The camera holds a static shot revealing the courtyard at slow speed.\n\n"
        "overall_soundscape: N/A\n\n"
        "non_diegetic_music: N/A"
    )
    # Unoverridden
    ctx_unoverridden = make_test_context(body)
    v1 = rule_pf04.validate(ctx_unoverridden)
    assert any(v.blocking is True for v in v1)
    assert any(v.overridden is False for v in v1)

    # Overridden with note in ctx.overrides
    ctx_overridden = make_test_context(body, overrides={"PF-04": {"note": "Artistic exemption"}})
    v2 = rule_pf04.validate(ctx_overridden)
    assert all(v.blocking is False for v in v2)
    assert any(v.overridden is True for v in v2)

@pytest.mark.asyncio
async def test_api_validation_routes(tmp_path):
    """Test FastAPI validation endpoints: validate-inputs, preflight, override, and vocab."""
    # Setup test DB clip and prompt
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM projects WHERE name = 'Test Stage 2'")
    cur.execute("INSERT INTO projects (name, notes, created_at, updated_at) VALUES ('Test Stage 2', '', 'now', 'now')")
    proj_id = cur.lastrowid

    cur.execute("""
        INSERT INTO clips (
            project_id, name, mode, h3_model, duration_s, resolution, ratio,
            audio_policy, style_id, plain_style_pair, inputs_revision, created_at, updated_at
        ) VALUES (?, 'Test Clip', 'T2VA', 'MiniMax-H3', 5, '768P', '16:9', 'dialogue_only', 'plain', 'Live-action, cinematic', 1, 'now', 'now')
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
        ) VALUES (?, 'gen-123', 'draft', 1, ?, ?, ?, '[]', 'now')
    """, (clip_id, test_prompt, test_prompt, len(test_prompt)))

    conn.commit()
    conn.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1:9013") as client:
        # 1. GET /api/vocab/camera_moves
        resp_vocab = await client.get("/api/vocab/camera_moves")
        assert resp_vocab.status_code == 200
        assert "The camera pushes in" in resp_vocab.json()["camera_patterns"]

        # 2. POST /api/clips/{id}/validate-inputs
        resp_inputs = await client.post(f"/api/clips/{clip_id}/validate-inputs")
        assert resp_inputs.status_code == 200
        # Valid clip inputs should have 0 blocking violations
        violations = resp_inputs.json()
        assert not any(v.get("blocking") for v in violations)

        # 3. POST /api/clips/{id}/preflight
        resp_preflight = await client.post(f"/api/clips/{clip_id}/preflight", json={"run_autofix": False})
        assert resp_preflight.status_code == 200
        preflight_violations = resp_preflight.json()
        assert isinstance(preflight_violations, list)

        # 4. POST /api/clips/{id}/override - Structural rule PF-01 must be REJECTED (400)
        resp_bad_override = await client.post(
            f"/api/clips/{clip_id}/override",
            json={"rule_id": "PF-01", "note": "Trying to override structural rule"},
        )
        assert resp_bad_override.status_code == 400
        assert "cannot be overridden" in resp_bad_override.json()["detail"]

        # 5. POST /api/clips/{id}/override - Heuristic rule PF-04 without note must be REJECTED (400)
        resp_no_note = await client.post(
            f"/api/clips/{clip_id}/override",
            json={"rule_id": "PF-04", "note": "   "},
        )
        assert resp_no_note.status_code == 400
        assert "mandatory explanation note is required" in resp_no_note.json()["detail"].lower()

        # 6. POST /api/clips/{id}/override - Valid heuristic override PF-04 with note -> SUCCESS (200)
        resp_good_override = await client.post(
            f"/api/clips/{clip_id}/override",
            json={"rule_id": "PF-04", "note": "Director requested custom motion modifier."},
        )
        assert resp_good_override.status_code == 200
        data = resp_good_override.json()
        assert data["status"] == "ok"
        assert data["rule_id"] == "PF-04"
