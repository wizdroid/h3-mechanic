"""Deterministic estimators and normalization conventions for H3 Prompt Studio (§9.5, §9.6)."""

from __future__ import annotations
import re
import unicodedata
from typing import Any, Optional, Union
from app.resources.vocab import get_scripts

ENGLISH_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")

# Words to exclude from sentence-ending dots
ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "st", "vs", "etc"}

def count_english_words(text: str) -> int:
    """Count regex matches of [A-Za-z0-9]+(?:'[A-Za-z]+)? in text."""
    if not text:
        return 0
    return len(ENGLISH_WORD_RE.findall(text))

def count_indic_syllables(text: str, language: str) -> int:
    """
    Count Indic syllables per §9.5/§9.6:
    Walk code points. Count a character when its category is Lo,
    it lies in the language script block, and the previous code point is not that virama.
    """
    if not text:
        return 0
    scripts = get_scripts()
    lang_info = scripts.get(language)
    if not lang_info or lang_info.get("virama") is None:
        # Fallback or English: not an Indic script
        return 0

    start = lang_info["range_start"]
    end = lang_info["range_end"]
    virama = lang_info["virama"]

    syllables = 0
    prev_cp: Optional[int] = None

    for char in text:
        cp = ord(char)
        cat = unicodedata.category(char)
        if cat == "Lo" and (start <= cp <= end):
            if prev_cp != virama:
                syllables += 1
        prev_cp = cp

    return syllables

def estimate_speech_tenths(text: str, language: str) -> int:
    """
    Speech duration in tenths of a second:
    English: speech_tenths = words * 4
    Other: speech_tenths = (syllables * 20 + 8) // 9
    """
    if language.lower() == "english":
        words = count_english_words(text)
        return words * 4
    else:
        syllables = count_indic_syllables(text, language)
        if syllables == 0:
            # If no Indic syllables found (e.g. English words inside tag), fallback to word count
            words = count_english_words(text)
            return words * 4
        return (syllables * 20 + 8) // 9

def estimate_line_duration_tenths(text: str, language: str) -> int:
    """line_tenths = speech_tenths + 5 (speech duration + 0.5s padding)."""
    return estimate_speech_tenths(text, language) + 5

def estimate_shot_min_duration_ms(lines: list[dict[str, Any]], pacing: str = "silent") -> int:
    """
    A shot with lines needs end_ms - start_ms >= (10 + sum(line_tenths)) * 100.
    A shot with no lines: silent needs at least 1500 ms, action at least 2500 ms.
    """
    if lines:
        total_line_tenths = sum(
            estimate_line_duration_tenths(line.get("text_raw", "") or line.get("text", ""), line.get("language", "English"))
            for line in lines
        )
        return (10 + total_line_tenths) * 100
    else:
        if pacing.lower() == "action":
            return 2500
        return 1500

def assign_speaker_numbers(lines: list[dict[str, Any]]) -> dict[int, int]:
    """
    Deterministic speaker numbers per §9.5:
    Sort lines by (shot.start_ms, line_order, id). Missing shot counts as start 0.
    Walk that list. First time a speakers.id appears, assign the next number from 1.
    If line has two speakers (e.g. simultaneous), assign both in ascending speaker id.
    Returns mapping: {speaker_id: assigned_number}.
    """
    sorted_lines = sorted(
        lines,
        key=lambda l: (
            l.get("shot_start_ms", 0) or 0,
            l.get("line_order", 0) or 0,
            l.get("id", 0) or 0,
        )
    )

    mapping: dict[int, int] = {}
    next_num = 1

    for line in sorted_lines:
        spk_id = line.get("speaker_id")
        spk_id_2 = line.get("speaker_id_2")

        spks_to_assign = []
        if spk_id is not None:
            spks_to_assign.append(spk_id)
        if spk_id_2 is not None and spk_id_2 != spk_id:
            spks_to_assign.append(spk_id_2)

        spks_to_assign.sort()

        for sid in spks_to_assign:
            if sid not in mapping:
                mapping[sid] = next_num
                next_num += 1

    return mapping

def normalize_text_raw(text: str) -> str:
    """
    Normalize text_raw per §9.5:
    Strip trailing whitespace. Replace trailing '।' or '॥' with '.'.
    If last character is not '.', '?', or '!', append '.'.
    """
    if not text:
        return "."
    s = text.rstrip()
    if s.endswith("।") or s.endswith("॥"):
        s = s[:-1] + "."
    if not s or s[-1] not in {".", "?", "!"}:
        s = s + "."
    return s

def format_ms_timestamp(ms: int) -> str:
    """Format milliseconds into MM:SS.mmm (e.g. 00:03.000)."""
    total_seconds = ms // 1000
    millis = ms % 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"

def count_sentences(text: str) -> int:
    """
    Count sentences per §9.6:
    Split field on [.!?] followed by whitespace or end,
    except a dot after Mr, Mrs, Ms, Dr, St, vs, or etc,
    and except a dot between digits.
    The count of pieces that contain a letter is the sentence count.
    """
    if not text or not text.strip():
        return 0

    pieces: list[str] = []
    n = len(text)
    last_idx = 0
    i = 0

    while i < n:
        ch = text[i]
        if ch in {".", "!", "?"}:
            # Check if followed by whitespace or string end
            is_end_of_field = (i + 1 == n) or text[i + 1].isspace()
            if is_end_of_field:
                is_exception = False
                if ch == ".":
                    # Check decimal digit between
                    if i > 0 and text[i - 1].isdigit() and (i + 1 < n and text[i + 1].isdigit()):
                        is_exception = True
                    # Check abbreviations before dot
                    # Look backwards for word
                    word_match = re.search(r"([A-Za-z]+)$", text[:i])
                    if word_match and word_match.group(1).lower() in ABBREVIATIONS:
                        is_exception = True

                if not is_exception:
                    pieces.append(text[last_idx:i + 1])
                    last_idx = i + 1
        i += 1

    if last_idx < n:
        pieces.append(text[last_idx:])

    count = 0
    for p in pieces:
        if re.search(r"[A-Za-z\u00C0-\u024F\u0900-\u0D7F]", p):
            count += 1

    return count

