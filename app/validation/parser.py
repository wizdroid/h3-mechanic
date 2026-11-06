"""Canonical unified prompt parser for H3 Prompt Studio (§9.6)."""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional
from app.resources.vocab import get_camera_moves

CUT_TIME_RE = re.compile(r"\[Shot (\d+)\] At (\d{2}):(\d{2})\.(\d{3}), the camera cuts to ")
CUT_TIME_WARN_RE = re.compile(r"\[Shot (\d+)\] At (\d{2}):(\d{2})\.(\d{3}), the shot cuts to ")
CUT_TIME_COLON_RE = re.compile(r"\[Shot (\d+)\] At (\d{2}):(\d{2}):(\d{3})")
SHOT_HEADER_GENERIC_RE = re.compile(r"\[Shot (\d+)\]")

DIALOGUE_SPAN_RE = re.compile(r"(<scenetrans>\s*)?<d>\[([^\]]+)\]\s*(.*?)</d>(\s*<cutoff>)?")
ONSCREEN_TEXT_RE = re.compile(r'"([^"\n]+)"')

LANDING_SUBSTRINGS = [" toward ", " revealing ", " onto ", " as "]
ALLOWED_MODIFIERS = [
    "with small amplitude",
    "with large amplitude",
    "at slow speed",
    "at fast speed",
]
ANY_MODIFIER_RE = re.compile(r"\b(at [a-z]+ speed|with [a-z]+ amplitude)\b", re.IGNORECASE)

@dataclass
class ParsedDialogueSpan:
    language: str
    text: str
    has_scenetrans: bool
    has_cutoff: bool
    full_span: str

@dataclass
class ParsedShot:
    number: int
    start_ms: Optional[int]
    cut_time_str: Optional[str]
    cut_wording_type: str  # "standard", "shot_cuts_to", "colon_timestamp", "invalid", "shot1"
    raw_header: str
    text: str
    camera_hits: list[str] = field(default_factory=list)
    camera_family: Optional[str] = None
    landing: Optional[str] = None
    modifiers: list[str] = field(default_factory=list)
    has_invalid_modifier: bool = False
    dialogue_spans: list[ParsedDialogueSpan] = field(default_factory=list)
    onscreen_texts: list[str] = field(default_factory=list)
    word_count: int = 0

@dataclass
class ParsedSection:
    name: str
    content: str
    lines: list[str] = field(default_factory=list)

@dataclass
class ParsedPrompt:
    raw_body: str
    detected_mode: Optional[str] = None
    instruction_line: Optional[str] = None
    sections: dict[str, ParsedSection] = field(default_factory=dict)
    shots: list[ParsedShot] = field(default_factory=list)
    style_line: Optional[str] = None
    has_carriage_return: bool = False
    has_feff: bool = False
    has_trailing_newline: bool = False
    lines_with_trailing_spaces: list[int] = field(default_factory=list)
    raw_line_breaks_in_desc: bool = False
    parsing_errors: list[str] = field(default_factory=list)

    def get_section_text(self, name: str) -> str:
        sec = self.sections.get(name)
        return sec.content if sec else ""

def _parse_camera_in_text(text: str, is_ref_mode: bool = True) -> tuple[list[str], Optional[str], Optional[str], list[str], bool]:
    """
    Scan text left to right for camera phrases from longest to shortest (§9.6).
    Returns (hits, family, landing, modifiers, has_invalid_modifier).
    """
    cam_data = get_camera_moves()
    patterns = list(cam_data["camera_patterns"])
    if not is_ref_mode:
        patterns.extend(cam_data.get("camera_patterns_non_ref", []))

    # Sort patterns from longest to shortest
    patterns.sort(key=len, reverse=True)

    compiled_patterns = []
    for pat in patterns:
        compiled_patterns.append((pat, re.compile(pat)))

    hits: list[str] = []
    # Left-to-right scan
    i = 0
    text_len = len(text)
    while i < text_len:
        hit_found = False
        sub = text[i:]
        for pat_str, regex in compiled_patterns:
            m = regex.match(sub)
            if m:
                matched_text = m.group(0)
                hits.append(matched_text)
                i += len(matched_text)
                hit_found = True
                break
        if not hit_found:
            i += 1

    landing: Optional[str] = None
    for lnd in LANDING_SUBSTRINGS:
        if lnd in text:
            landing = lnd.strip()
            break

    # Determine move family if exactly one hit
    family: Optional[str] = None
    if len(hits) == 1:
        h = hits[0].lower()
        if "static" in h:
            family = "static"
        elif "point of view" in h or "pov" in h:
            family = "pov"
        elif "shakes" in h or "shake" in h:
            family = "shake"
        elif "pushes in" in h:
            family = "push"
        elif "pulls out" in h:
            family = "pull"
        elif "zooms in" in h:
            family = "zoom_in"
        elif "zooms out" in h:
            family = "zoom_out"
        elif "pans left" in h or "pans right" in h:
            family = "pan"
        elif "tilts" in h:
            family = "tilt"
        elif "trucks" in h:
            family = "truck"
        elif "pedestals" in h:
            family = "pedestal"
        elif "arcs" in h:
            family = "arc"
        elif "tracks" in h:
            family = "track"
        elif "rolls" in h:
            family = "roll"

    modifiers: list[str] = []
    has_invalid_modifier = False

    for mod in ALLOWED_MODIFIERS:
        if mod in text:
            modifiers.append(mod)

    # Check for any other amplitude or speed phrases
    all_mod_matches = ANY_MODIFIER_RE.findall(text)
    for m in all_mod_matches:
        if m.lower() not in [am.lower() for am in ALLOWED_MODIFIERS]:
            has_invalid_modifier = True
            modifiers.append(m)

    return hits, family, landing, modifiers, has_invalid_modifier

def _parse_shot_text(shot_num: int, header: str, wording_type: str, time_str: Optional[str], time_ms: Optional[int], prose: str, is_ref_mode: bool) -> ParsedShot:
    cam_hits, cam_family, landing, modifiers, invalid_mod = _parse_camera_in_text(prose, is_ref_mode)

    dialogue_spans: list[ParsedDialogueSpan] = []
    for m in DIALOGUE_SPAN_RE.finditer(prose):
        scenetrans = bool(m.group(1))
        lang = m.group(2).strip()
        d_text = m.group(3).strip()
        cutoff = bool(m.group(4))
        dialogue_spans.append(
            ParsedDialogueSpan(
                language=lang,
                text=d_text,
                has_scenetrans=scenetrans,
                has_cutoff=cutoff,
                full_span=m.group(0),
            )
        )

    onscreen_texts = ONSCREEN_TEXT_RE.findall(prose)
    word_count = len(prose.split())

    return ParsedShot(
        number=shot_num,
        start_ms=time_ms,
        cut_time_str=time_str,
        cut_wording_type=wording_type,
        raw_header=header,
        text=prose,
        camera_hits=cam_hits,
        camera_family=cam_family,
        landing=landing,
        modifiers=modifiers,
        has_invalid_modifier=invalid_mod,
        dialogue_spans=dialogue_spans,
        onscreen_texts=onscreen_texts,
        word_count=word_count,
    )

def parse_prompt(body: str) -> ParsedPrompt:
    """
    Parse a raw prompt body into a unified ParsedPrompt structure.
    Strictly follows §9.6 parser specification.
    """
    has_cr = "\r" in body
    has_feff = "\ufeff" in body
    has_trailing_newline = body.endswith("\n")

    clean_body = body.replace("\r", "")
    lines = clean_body.split("\n")

    lines_with_trailing_spaces = [
        idx + 1 for idx, l in enumerate(lines) if l.endswith(" ") or l.endswith("\t")
    ]

    parsed = ParsedPrompt(
        raw_body=body,
        has_carriage_return=has_cr,
        has_feff=has_feff,
        has_trailing_newline=has_trailing_newline,
        lines_with_trailing_spaces=lines_with_trailing_spaces,
    )

    if not body.strip():
        parsed.parsing_errors.append("Empty prompt body")
        return parsed

    # Mode detection
    first_line = lines[0] if lines else ""
    if first_line == "subject_definitions:":
        parsed.detected_mode = "REF2VA"
    elif first_line.startswith("integrated_multimodal_description: "):
        parsed.detected_mode = "T2VA"
    elif first_line.startswith("For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."):
        parsed.detected_mode = "I2VA"
        parsed.instruction_line = first_line
    elif first_line.startswith("How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video;"):
        parsed.detected_mode = "FL2VA"
        parsed.instruction_line = first_line
    elif first_line.startswith("How the reference pictures align with the target video — <Picture 1> (from [Shot N])") or (
        first_line.startswith("How the reference pictures align with the target video — <Picture 1> (from [Shot ") and "aligns with the" in first_line
    ):
        parsed.detected_mode = "L2VA"
        parsed.instruction_line = first_line
    else:
        # Fallback heuristic: check if any instruction line or section exists
        if "subject_definitions:" in body:
            parsed.detected_mode = "REF2VA"
        elif "integrated_multimodal_description:" in body:
            parsed.detected_mode = "T2VA"

    is_ref = parsed.detected_mode == "REF2VA"

    if is_ref:
        _parse_ref2va(parsed, clean_body)
    else:
        _parse_t2va_and_frames(parsed, clean_body)

    return parsed

def _parse_ref2va(parsed: ParsedPrompt, body: str) -> None:
    """Parse REF2VA six-section layout (§9.6)."""
    # Sections: subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music
    sections_order = [
        "subject_definitions",
        "summary",
        "retention_analysis",
        "detailed_description",
        "overall_soundscape",
        "non_diegetic_music",
    ]

    # Split on double newlines
    blocks = re.split(r"\n\n+", body.strip())
    # Match headers
    header_re = re.compile(r"^([a-z_]+):\s*\n?", re.MULTILINE)

    # Let's extract sections cleanly by scanning headers
    header_indices = []
    for sec_name in sections_order:
        header_str = f"{sec_name}:"
        idx = body.find(header_str)
        if idx != -1:
            header_indices.append((idx, sec_name))

    header_indices.sort()

    for i, (idx, sec_name) in enumerate(header_indices):
        start_pos = idx + len(sec_name) + 1
        end_pos = header_indices[i + 1][0] if i + 1 < len(header_indices) else len(body)
        raw_content = body[start_pos:end_pos].strip("\n")
        lines = [l for l in raw_content.split("\n") if l]
        parsed.sections[sec_name] = ParsedSection(name=sec_name, content=raw_content.strip(), lines=lines)

    # Detailed description breakdown
    det_sec = parsed.sections.get("detailed_description")
    if det_sec and det_sec.content:
        det_lines = [l.strip() for l in det_sec.content.split("\n") if l.strip()]
        if det_lines:
            # First line is style line
            if not det_lines[0].startswith("[Shot"):
                parsed.style_line = det_lines[0]
                shot_lines = det_lines[1:]
            else:
                shot_lines = det_lines

            _parse_shots_from_lines(parsed, shot_lines, is_ref_mode=True)

def _parse_t2va_and_frames(parsed: ParsedPrompt, body: str) -> None:
    """Parse T2VA and frame modes (§9.6)."""
    clean_body = body
    if parsed.instruction_line:
        # Strip instruction line and following blank lines
        clean_body = clean_body[len(parsed.instruction_line):].lstrip("\n")

    # Three fields: integrated_multimodal_description, overall_soundscape, non_diegetic_music
    field_names = ["integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"]
    field_re = re.compile(r"^(integrated_multimodal_description|overall_soundscape|non_diegetic_music):\s*(.*)$", re.MULTILINE)

    matches = list(field_re.finditer(clean_body))
    for m in matches:
        sec_name = m.group(1)
        content = m.group(2).strip()
        parsed.sections[sec_name] = ParsedSection(name=sec_name, content=content, lines=[content])

    # Parse shots from integrated_multimodal_description
    desc_sec = parsed.sections.get("integrated_multimodal_description")
    if desc_sec and desc_sec.content:
        # Check raw line breaks in description
        if "\n" in desc_sec.content:
            parsed.raw_line_breaks_in_desc = True

        desc_text = desc_sec.content
        _parse_shots_from_text(parsed, desc_text, is_ref_mode=False)

def _parse_shots_from_text(parsed: ParsedPrompt, text: str, is_ref_mode: bool) -> None:
    """Parse [Shot 1] ... [Shot N] from a continuous text block."""
    shot_matches = list(SHOT_HEADER_GENERIC_RE.finditer(text))
    if not shot_matches:
        return

    for i, m in enumerate(shot_matches):
        shot_num = int(m.group(1))
        start_idx = m.start()
        end_idx = shot_matches[i + 1].start() if i + 1 < len(shot_matches) else len(text)
        shot_block = text[start_idx:end_idx].strip()

        _parse_individual_shot_block(parsed, shot_num, shot_block, is_ref_mode)

def _parse_shots_from_lines(parsed: ParsedPrompt, lines: list[str], is_ref_mode: bool) -> None:
    """Parse shots where each shot is on its own line (REF2VA)."""
    for l in lines:
        m = SHOT_HEADER_GENERIC_RE.search(l)
        if m:
            shot_num = int(m.group(1))
            _parse_individual_shot_block(parsed, shot_num, l.strip(), is_ref_mode)

def _parse_individual_shot_block(parsed: ParsedPrompt, shot_num: int, shot_block: str, is_ref_mode: bool) -> None:
    wording_type = "invalid"
    time_str = None
    time_ms = None
    header = f"[Shot {shot_num}]"
    prose = shot_block

    if shot_num == 1:
        if shot_block.startswith("[Shot 1]"):
            header = "[Shot 1]"
            rest = shot_block[len("[Shot 1]"):].lstrip()
            if rest.startswith("At ") or CUT_TIME_RE.search(shot_block) or CUT_TIME_WARN_RE.search(shot_block):
                wording_type = "invalid_timestamp_in_shot1"
                m_cut = re.search(r"At (\d{2}):(\d{2})[.:](\d{3})", shot_block)
                if m_cut:
                    time_str = f"{m_cut.group(1)}:{m_cut.group(2)}.{m_cut.group(3)}"
                    time_ms = int(m_cut.group(1)) * 60000 + int(m_cut.group(2)) * 1000 + int(m_cut.group(3))
            else:
                wording_type = "shot1"
            prose = rest
    else:
        m_std = CUT_TIME_RE.match(shot_block)
        m_warn = CUT_TIME_WARN_RE.match(shot_block)
        m_col = CUT_TIME_COLON_RE.match(shot_block)

        if m_std:
            wording_type = "standard"
            minutes = int(m_std.group(2))
            seconds = int(m_std.group(3))
            millis = int(m_std.group(4))
            time_str = f"{minutes:02d}:{seconds:02d}.{millis:03d}"
            time_ms = minutes * 60000 + seconds * 1000 + millis
            header = m_std.group(0).rstrip()
            prose = shot_block[len(m_std.group(0)):].lstrip()
        elif m_warn:
            wording_type = "shot_cuts_to"
            minutes = int(m_warn.group(2))
            seconds = int(m_warn.group(3))
            millis = int(m_warn.group(4))
            time_str = f"{minutes:02d}:{seconds:02d}.{millis:03d}"
            time_ms = minutes * 60000 + seconds * 1000 + millis
            header = m_warn.group(0).rstrip()
            prose = shot_block[len(m_warn.group(0)):].lstrip()
        elif m_col:
            wording_type = "colon_timestamp"
            header = m_col.group(0).rstrip()
            prose = shot_block[len(m_col.group(0)):].lstrip()
        else:
            wording_type = "invalid"
            # Just take [Shot N] as header
            m_gen = SHOT_HEADER_GENERIC_RE.match(shot_block)
            if m_gen:
                header = m_gen.group(0)
                prose = shot_block[len(header):].lstrip()

    parsed_shot = _parse_shot_text(
        shot_num=shot_num,
        header=header,
        wording_type=wording_type,
        time_str=time_str,
        time_ms=time_ms,
        prose=prose,
        is_ref_mode=is_ref_mode,
    )
    parsed.shots.append(parsed_shot)
