"""Deterministic 5-step autofix engine for H3 Prompt Studio (§9.6, S-06)."""

from __future__ import annotations
import re
from app.resources.vocab import HOUSE_SENTENCE

# Explicit camera phrases to capitalize in Pass 3
CAMERA_PHRASES_TO_CAPITALIZE = [
    ("the camera holds a static shot", "The camera holds a static shot"),
    ("the camera pushes in", "The camera pushes in"),
    ("the camera pulls out", "The camera pulls out"),
    ("the camera zooms in", "The camera zooms in"),
    ("the camera zooms out", "The camera zooms out"),
    ("the camera pans left", "The camera pans left"),
    ("the camera pans right", "The camera pans right"),
    ("the camera tilts up", "The camera tilts up"),
    ("the camera tilts down", "The camera tilts down"),
    ("the camera trucks left", "The camera trucks left"),
    ("the camera trucks right", "The camera trucks right"),
    ("the camera pedestals up", "The camera pedestals up"),
    ("the camera pedestals down", "The camera pedestals down"),
    ("the camera shakes slightly", "The camera shakes slightly"),
    ("the camera shakes strongly", "The camera shakes strongly"),
    ("the camera rolls clockwise", "The camera rolls clockwise"),
    ("the camera rolls counterclockwise", "The camera rolls counterclockwise"),
    ("the camera arcs around", "The camera arcs around"),
    ("the camera tracks", "The camera tracks"),
]

def run_deterministic_autofix(body: str, audio_policy: str = "dialogue_only", mode: str = "T2VA") -> str:
    """
    Run the 5 deterministic autofix passes in order (§9.6).
    Re-parses after passes as needed.
    """
    if not body:
        return body

    current = body

    # Pass 1: In a shot header, replace At (\d{2}):(\d{2}):(\d{3}) with At \1:\2.\3
    current = re.sub(r"At (\d{2}):(\d{2}):(\d{3})", r"At \1:\2.\3", current)

    # Pass 2: Replace 'the shot cuts to' with 'the camera cuts to' when it follows a legal timestamp
    current = re.sub(
        r"(At \d{2}:\d{2}\.\d{3},\s*)the shot cuts to",
        r"\1the camera cuts to",
        current,
    )

    # Pass 3: Replace a lowercase official camera phrase with the capitalized phrase from table
    for lower_p, cap_p in CAMERA_PHRASES_TO_CAPITALIZE:
        # After sentence boundary
        current = re.sub(
            rf"(?<=[.!?\n]\s){re.escape(lower_p)}",
            lambda m, rep=cap_p: rep,
            current,
        )
        # After cuts to
        current = re.sub(
            rf"(cuts to\s+){re.escape(lower_p)}",
            lambda m, rep=cap_p: m.group(1) + rep,
            current,
        )
        # At start of line / text
        current = re.sub(
            rf"(?m)^{re.escape(lower_p)}",
            lambda m, rep=cap_p: rep,
            current,
        )

    # Pass 4: Replace ':' immediately before '<d>' with ','
    current = re.sub(r":(\s*<d>)", r",\1", current)

    # Pass 5: Audio policy normalization (S-06)
    is_ref = "subject_definitions:" in current or mode == "REF2VA"

    if audio_policy == "dialogue_only":
        current = _set_sound_fields_na(current, is_ref)
        current = _ensure_house_sentence_dialogue_only(current, is_ref)
    elif audio_policy == "silence":
        current = _set_sound_fields_na(current, is_ref)
        current = _remove_house_sentence(current)
    elif audio_policy == "custom":
        current = _remove_house_sentence(current)

    return current

def _set_sound_fields_na(body: str, is_ref: bool) -> str:
    """Set sound fields to N/A for both single-line and multiline formats (S-06)."""
    current = body

    if is_ref:
        # Multiline REF2VA: overall_soundscape:\n<content> -> overall_soundscape:\nN/A
        current = re.sub(
            r"overall_soundscape:\s*.*?(?=\n\n|\Z)",
            "overall_soundscape:\nN/A",
            current,
            flags=re.DOTALL,
        )
        current = re.sub(
            r"non_diegetic_music:\s*.*?(?=\n\n|\Z)",
            "non_diegetic_music:\nN/A",
            current,
            flags=re.DOTALL,
        )
    else:
        # Single line T2VA/frames: overall_soundscape: <content>
        current = re.sub(r"overall_soundscape:\s*.*?(?=\n|$)", "overall_soundscape: N/A", current)
        current = re.sub(r"non_diegetic_music:\s*.*?(?=\n|$)", "non_diegetic_music: N/A", current)

    return current

def _ensure_house_sentence_dialogue_only(body: str, is_ref: bool) -> str:
    """Ensure house sentence occurs once at §7.6 position."""
    if HOUSE_SENTENCE in body:
        # Already present, return as is
        return body

    if is_ref:
        # REF2VA: last sentence of style line before \n[Shot 1]
        m = re.search(r"(detailed_description:\s*\n)(.*?)(?=\n\[Shot 1\])", body, re.DOTALL)
        if m:
            prefix = m.group(1)
            style_content = m.group(2).strip()
            if not style_content.endswith("."):
                style_content += "."
            new_style = f"{style_content} {HOUSE_SENTENCE}"
            body = body[:m.start()] + prefix + new_style + body[m.end():]
    else:
        # T2VA / frame modes: immediately after the first sentence of [Shot 1]
        # Match [Shot 1] <first sentence>[.!?]
        m = re.search(r"(\[Shot 1\]\s*[^.!?]+[.!?])", body)
        if m:
            first_sentence = m.group(1)
            body = body.replace(first_sentence, f"{first_sentence} {HOUSE_SENTENCE}", 1)

    return body

def _remove_house_sentence(body: str) -> str:
    """Remove house sentence if present and clean whitespace."""
    if HOUSE_SENTENCE not in body:
        return body
    cleaned = body.replace(f" {HOUSE_SENTENCE}", "").replace(HOUSE_SENTENCE, "")
    # Clean up any resulting double spaces
    cleaned = re.sub(r"[ ]{2,}", " ", cleaned)
    return cleaned
