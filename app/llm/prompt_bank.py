"""Meta-Prompt Templates, JSON Schemas, and Word Caps (§5.5, §8.0–§8.9).

Contains:
- Canonical JSON schemas for structured output stages
- Word caps and num_predict calculation helpers
- Meta-prompt template strings with {{var}} substitutions
"""

from __future__ import annotations
import math
from typing import Any

# ============================================================================
# 1. JSON SCHEMAS FOR STRUCTURED DECODING
# ============================================================================

PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "characters",
        "setting",
        "beats",
        "shots",
        "voices",
    ],
    "properties": {
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["speaker_key", "persona"],
                "properties": {
                    "speaker_key": {"type": "string"},
                    "persona": {"type": "string", "maxLength": 80},
                },
            },
        },
        "setting": {"type": "string"},
        "beats": {
            "type": "array",
            "items": {"type": "string"},
        },
        "shots": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "start_s",
                    "end_s",
                    "size",
                    "angle",
                    "camera_phrase",
                    "pacing",
                    "line_ids",
                ],
                "properties": {
                    "start_s": {"type": "number"},
                    "end_s": {"type": "number"},
                    "size": {"type": "string"},
                    "angle": {"type": "string"},
                    "camera_phrase": {"type": "string"},
                    "landing": {"type": "string"},
                    "pacing": {"enum": ["silent", "action"]},
                    "events": {"type": "string"},
                    "action_chain": {"type": "string"},
                    "expression": {"type": "string"},
                    "line_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "voices": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["speaker_key", "voice"],
                "properties": {
                    "speaker_key": {"type": "string"},
                    "voice": {"type": "string"},
                },
            },
        },
    },
}

RETENTION_REASONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reasons"],
    "properties": {
        "reasons": {
            "type": "array",
            "items": {"type": "string", "maxLength": 160},
        },
    },
}

# ============================================================================
# 2. WORD CAPS & NUM_PREDICT CALCULATORS (§5.5)
# ============================================================================

def calculate_num_predict(stage_id: str, context: dict[str, Any]) -> int:
    """
    Calculate num_predict = ceil(word_cap * 2.2) per §5.5 table.
    """
    if stage_id == "seed_elaboration":
        word_cap = 320
    elif stage_id == "frame_action_elaboration":
        word_cap = 260
    elif stage_id == "prose_writer":
        target = context.get("word_target", 180)
        word_cap = target * 1.4
    elif stage_id == "shot_writer":
        word_cap = 560
    elif stage_id == "summary_writer":
        word_cap = 90
    elif stage_id == "retention_writer":
        empty_count = context.get("empty_reason_count", 1)
        word_cap = 25 * max(empty_count, 1)
    elif stage_id == "preflight_fixer":
        template_words = len(context.get("template_text", "").split())
        word_cap = template_words + 200
    elif stage_id == "safer_framing":
        template_words = len(context.get("template_text", "").split())
        word_cap = template_words + 80
    else:
        word_cap = 256

    return int(math.ceil(word_cap * 2.2))

# ============================================================================
# 3. META-PROMPT TEMPLATES (§8.0–§8.9)
# ============================================================================

SEED_ELABORATION_PROMPT = """Expand a brief into a scene plan for a video AI. Reply JSON only, matching the schema.
Seed: {seed}  Duration: {duration_s}s  Ratio: {ratio}  Style opening: {style_opening}
Lines (placeholders only): {line_stubs}   Voice library ids: {voice_ids}
Keys: characters, setting, beats, shots, voices.
Rules: beats are causal chains (initial state, trigger, action, reaction). shots: count per {shot_budget}; each has start_s, end_s, size, angle, pacing, camera_phrase from {verbs} with landing, and line_ids. voices: one library id from {voice_ids} per speaker. Do not invent prose voices. Prose is English. Max 320 words."""

FRAME_ACTION_PROMPT = """Mode: {mode}. Frames: {frames}. Action: {action}. Duration: {duration_s}s. Style opening: {style_opening}
Lines (placeholders only): {line_stubs}
Write the motion plan as JSON shots. Use exactly {shot_count} shots. I2VA: from frame state → onset → development → result. FL2VA: describe motion between the frames; the final shot lands on the last frame. L2VA: precede, act, converge onto the last frame.
Per shot: start_s, end_s, composition, action_chain, camera (one verb from {verbs} with direction and landing), expression per readable face, line placeholders. First shot starts 0.0. Prose is English. Max 260 words."""

PROSE_WRITER_PROMPT = """Write the shots of a video prompt from this plan: {plan_json}. Style opening: {style_opening}
Output the integrated_multimodal_description paragraph only. Start with the style opening, then [Shot 1] (untimed), then for each later shot "[Shot N] At {cut_time_n}, the camera cuts to".
Per shot: framing and subject position, light, one causal action chain with physical feedback, exactly the planned camera move with landing, an expression for each readable face, and each planned line only as {sample_placeholder}. Do not write a speaker, a voice, a delivery, mouth closure, or any non-English text. {sample_placeholder} expands to the speech sentence. No sound descriptions. {mode_path_rule}
Target {word_target} words. Plain text, one paragraph."""

SHOT_WRITER_PROMPT = """Write detailed_description for the plan: {plan}. Style sentence: {style_opening}
Put the style sentence before [Shot 1]. It starts "The target video is".
Per shot: "[Shot 1]" alone; "[Shot N] At {cut_time_n}, the camera cuts to" for N>1 (use the given times exactly).
Content per shot: composition and size, subject labels, light, one causal action chain with physical feedback, the planned camera move with landing, an expression per readable face, and each line only as {sample_placeholder}. Do not write a speaker tag, a voice, a delivery, mouth closure, or any quoted or non-English text.
Readable or speaking faces: close-up/medium close-up/medium, front or three-quarter; wide only from behind or with no readable faces.
{audio_policy_line}
Target {word_target} words. Plain text."""

SUMMARY_WRITER_PROMPT = """Write the summary section for this video generation plan: {plan}.
Open with exactly [{task_type}].
Follow with one concise paragraph describing how the target video relates to the references.
Use only the defined subject labels: {subject_labels}. Do not describe scenes not in the plan.
Target 50–90 words. Plain text."""

RETENTION_WRITER_PROMPT = """Write concise reference retention reasons for this video plan. Reply JSON only matching schema:
Plan: {plan}
Items needing reasons: {items_to_justify}
Output: {{"reasons": ["one reason of about 20 words per item", ...]}}"""

PREFLIGHT_FIXER_PROMPT = """Fix this {mode} prompt template. Violations: {violations}
Apply only these fixes. Keep every {{{{...}}}} placeholder, shot header, timestamp, label and unflagged sentence unchanged. Output the fixed template only."""

SAFER_FRAMING_PROMPT = """Rewrite only shot size and angle in this {mode} prompt template.
Move every readable or speaking face to a close-up, medium close-up, or medium shot, front-facing or three-quarter.
Keep every {{{{...}}}} placeholder, speaker id, label, timestamp, field name and camera verb unchanged.
Output the full template only."""
