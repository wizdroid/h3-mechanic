"""Deterministic Prompt Assembler and Renderer (§8.0, §8.7, S-04, S-05).

The ONLY assembler in v1:
- Builds exact instruction lines for I2VA, FL2VA, L2VA
- Expands dialogue placeholders ({{Lk}}) into canonical 8-part speech sentences
- Expands on-screen text placeholders ({{Tm}})
- S-04: Places cross-cut prefix immediately after the cut header for destination shots N > 1
- S-05: Fallback prose stitcher guaranteeing placeholder preservation without omission
- Inserts dialogue-only house sentence at exact §7.6 positions
- Enforces single-line field format for T2VA/frames and 6-section format for REF2VA
"""

from __future__ import annotations
import re
from typing import Any, Optional

from app.resources.vocab import (
    HOUSE_SENTENCE,
    get_voices,
    get_deliveries,
    get_styles,
)
from app.validation.estimators import (
    assign_speaker_numbers,
    normalize_text_raw,
    format_ms_timestamp,
)
from app.engine.placeholders import (
    build_placeholder_maps,
    validate_template_integrity,
    PLACEHOLDER_LK_RE,
    PLACEHOLDER_TM_RE,
)
from app.engine.subject_builder import build_subject_definitions, ROLE_DISPLAY_NAMES

CANONICAL_TASK_TYPE_ORDER = [
    "reference generation",
    "keyframe completion",
    "video editing",
    "video continuation",
    "audio reuse",
    "audio reference",
]

def derive_task_types(
    clip: dict[str, Any],
    references: list[dict[str, Any]],
    subject_pictures: list[dict[str, Any]],
    speakers: list[dict[str, Any]],
) -> list[str]:
    """
    Derive the ordered task types per §6.4, §8.5, and Appendix A.9.
    Canonical Order: reference generation, keyframe completion, video editing, video continuation, audio reuse, audio reference.
    """
    # 1. If user touched task types, respect user choice
    if clip.get("task_types_touched"):
        raw_types = clip.get("task_types_json", "[]")
        if isinstance(raw_types, str):
            try:
                import json
                user_types = json.loads(raw_types)
            except Exception:
                user_types = []
        else:
            user_types = list(raw_types)

        ordered = [t for t in CANONICAL_TASK_TYPE_ORDER if t in user_types]
        if ordered:
            return ordered

    # 2. Otherwise auto-derive defaults
    derived: set[str] = set()

    # Any guidance reference -> reference generation
    # Any frame/composition anchor -> keyframe completion
    has_guidance = False
    has_keyframe = False
    for sp in subject_pictures:
        r_role = sp.get("reference_role", "")
        if r_role in {"first_frame", "keyframe", "last_frame", "composition_anchor", "framing_reference"}:
            has_keyframe = True
        else:
            has_guidance = True

    # If images exist with no specific link yet, count as guidance
    image_refs = [r for r in references if r.get("kind") == "image"]
    if image_refs and not has_keyframe and not has_guidance:
        has_guidance = True
    elif image_refs and not has_keyframe:
        has_guidance = True

    if has_guidance or not has_keyframe:
        derived.add("reference generation")
    if has_keyframe:
        derived.add("keyframe completion")

    # Audio used only for timbre -> audio reference
    audio_refs = [r for r in references if r.get("kind") == "audio"]
    has_timbre_audio = False
    for spk in speakers:
        if spk.get("audio_reference_id"):
            has_timbre_audio = True
            break
    if has_timbre_audio or audio_refs:
        derived.add("audio reference")

    # Also check if clip had manual user flags like video editing / video continuation / audio reuse
    raw_types = clip.get("task_types_json", "[]")
    if isinstance(raw_types, str):
        try:
            import json
            prev_types = json.loads(raw_types)
        except Exception:
            prev_types = []
    else:
        prev_types = list(raw_types)

    for manual_type in ("video editing", "video continuation", "audio reuse"):
        if manual_type in prev_types:
            derived.add(manual_type)

    ordered = [t for t in CANONICAL_TASK_TYPE_ORDER if t in derived]
    return ordered if ordered else ["reference generation"]

def build_retention_analysis_section(
    subjects: list[dict[str, Any]],
    references: list[dict[str, Any]],
    subject_pictures: list[dict[str, Any]],
    planned_shots: list[dict[str, Any]],
    retention_entries: Optional[list[dict[str, Any]]] = None,
    task_types: Optional[list[str]] = None,
) -> str:
    """
    Build retention_analysis section lines per §8.6 and Appendix A.9.
    No (Sx) tags permitted (PF-22).
    """
    ref_by_id = {r.get("id"): r for r in references}
    subj_by_id = {s.get("id"): s for s in subjects}

    lines: list[str] = []

    if retention_entries:
        for entry in retention_entries:
            marker = entry.get("marker", "fully_preserved").strip()
            reason = (entry.get("reason") or "Key visual attributes and features are maintained.").strip()
            if not reason.endswith("."):
                reason += "."
            # Ensure no (Sx) in retention
            reason = re.sub(r"\(S\d+(?:,S\d+)?\)", "", reason).strip()

            sid = entry.get("subject_id")
            rid = entry.get("reference_id")

            if sid and sid in subj_by_id:
                s = subj_by_id[sid]
                s_ord = s.get("ordinal", 1)
                parenthetical = entry.get("parenthetical") or "(appears in [Shot 1])"
                p_clean = parenthetical.strip()
                if not p_clean.startswith("("):
                    p_clean = f"({p_clean})"
                lines.append(f"<Subject {s_ord}> {p_clean}: {marker} - {reason}")
            elif rid and rid in ref_by_id:
                ref = ref_by_id[rid]
                kind = ref.get("kind", "image")
                ord_num = ref.get("ordinal", 1)

                if kind == "image":
                    parenthetical = entry.get("parenthetical") or "[Shot 1] first frame"
                    p_clean = parenthetical.strip()
                    if not p_clean.startswith("("):
                        p_clean = f"({p_clean})"
                    lines.append(f"<Picture {ord_num}> {p_clean}: {marker} - {reason}")
                elif kind == "video":
                    parenthetical = entry.get("parenthetical") or "cut and pacing structure"
                    p_clean = parenthetical.strip()
                    if not p_clean.startswith("("):
                        p_clean = f"({p_clean})"
                    lines.append(f"<Video {ord_num}> {p_clean}: {marker} - {reason}")
                elif kind == "audio":
                    lines.append(f"<Audio {ord_num}>: {marker} - {reason}")
    else:
        # Default generation
        # 1. Subjects
        for s in sorted(subjects, key=lambda x: x.get("ordinal", 1)):
            s_ord = s.get("ordinal", 1)
            role = (s.get("role") or "person").lower()
            default_marker = "partially_preserved" if role in {"outfit", "prop", "accessory"} else "fully_preserved"
            lines.append(f"<Subject {s_ord}> (appears in [Shot 1]): {default_marker} - Key visual attributes and features are maintained.")

        # 2. Picture Anchors
        for sp in subject_pictures:
            r_role = sp.get("reference_role", "")
            if r_role in {"first_frame", "keyframe", "last_frame", "composition_anchor", "framing_reference"}:
                ref = ref_by_id.get(sp.get("reference_id"))
                if ref and ref.get("kind") == "image":
                    p_ord = ref.get("ordinal", 1)
                    role_name = ROLE_DISPLAY_NAMES.get(r_role, r_role)
                    shot_ord = sp.get("anchor_shot_ordinal") or 1
                    lines.append(f"<Picture {p_ord}> ([Shot {shot_ord}] {role_name}): fully_preserved - Defines camera framing and visual anchor position.")

        # 3. Videos
        for r in references:
            if r.get("kind") == "video":
                v_ord = r.get("ordinal", 1)
                lines.append(f"<Video {v_ord}> (cut and pacing structure): weak_reference - Cut pacing and timing structure inform sequence flow.")

        # 4. Audios
        for r in references:
            if r.get("kind") == "audio":
                a_ord = r.get("ordinal", 1)
                is_reuse = task_types and "audio reuse" in task_types
                marker = "fully_copy" if is_reuse else "reference"
                reason = "Audio signal is reused directly." if is_reuse else "Acoustic delivery and timbre match dialogue lines."
                lines.append(f"<Audio {a_ord}>: {marker} - {reason}")

    return "\n".join(lines)

CUT_HEADER_RE = re.compile(r"(\[Shot (\d+)\] At \d{2}:\d{2}\.\d{3}, the camera cuts to )")
SHOT1_HEADER_RE = re.compile(r"(\[Shot 1\]\s*)")

def build_instruction_line(mode: str, shot_count: int, duration_s: int) -> Optional[str]:
    """
    Build the exact instruction line per Appendix A.2:
    - I2VA: Picture 1 (from [Shot 1]) fully referenced at 0.00
    - FL2VA: Picture 1 aligns with 0.00; Picture 2 aligns with S.SS (no angle/square brackets; em dash U+2014)
    - L2VA: <Picture 1> (from [Shot N]) aligns with S.SS (em dash U+2014)
    """
    s_ss = f"{duration_s}.00"
    if mode == "I2VA":
        return "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
    elif mode == "FL2VA":
        return f"How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot {shot_count}) aligns with the {s_ss}-second mark of the target video."
    elif mode == "L2VA":
        return f"How the reference pictures align with the target video — <Picture 1> (from [Shot {shot_count}]) aligns with the {s_ss}-second mark of the target video."
    return None

def expand_speech_sentence(
    line: dict[str, Any],
    mode: str,
    speaker_id_to_num: dict[int, int],
    speakers_by_id: dict[int, dict[str, Any]],
    subjects_by_id: dict[int, dict[str, Any]],
    references_by_id: dict[int, dict[str, Any]],
) -> str:
    """
    Expand {{Lk}} to the canonical 8-part speech sentence (§8.0):
    1. Speaker reference (<Subject N> or The {persona})
    2. Speaker tag ( (S1) or (S1,S2) )
    3. Verb (says in an off-screen voiceover or delivery verb)
    4. Voice phrase (library phrase or in the voice timbre referenced from <Audio N>)
    5. Accent clause (, with a natural Bengaluru urban accent)
    6. Delivery manner (, breath hitching between words)
    7. Spoken dialogue (<scenetrans>? <d>[Language] text</d> <cutoff>?)
    8. Lip closure sentence / clause
    """
    spk_id = line.get("speaker_id")
    spk_id_2 = line.get("speaker_id_2")

    spk1 = speakers_by_id.get(spk_id, {})
    spk2 = speakers_by_id.get(spk_id_2, {}) if spk_id_2 else None

    # 1. Speaker reference
    def _format_single_ref(spk: dict[str, Any]) -> tuple[str, str]:
        # returns (ref_string, pronoun)
        subj_id = spk.get("subject_id")
        subj = subjects_by_id.get(subj_id) if subj_id else None

        pronoun = "his"
        if subj:
            pronoun = subj.get("pronoun", "his")
        elif spk.get("pronoun"):
            pronoun = spk.get("pronoun", "his")

        if mode == "REF2VA":
            if subj:
                return f"<Subject {subj.get('ordinal', 1)}>", pronoun
            else:
                persona = (spk.get("persona") or spk.get("display_name") or "the speaker").strip()
                return persona, pronoun
        else:
            persona = (spk.get("persona") or spk.get("display_name") or "the speaker").strip()
            if persona.lower().startswith("the "):
                return persona, pronoun
            else:
                return f"The {persona}", pronoun

    ref1, pron1 = _format_single_ref(spk1)
    if spk2:
        ref2, pron2 = _format_single_ref(spk2)
        speaker_ref = f"{ref1} and {ref2}"
    else:
        speaker_ref = ref1

    # 2. Speaker tag
    n1 = speaker_id_to_num.get(spk_id, 1)
    if spk2:
        n2 = speaker_id_to_num.get(spk_id_2, 2)
        low, high = sorted([n1, n2])
        speaker_tag = f" (S{low},S{high})"
    else:
        speaker_tag = f" (S{n1})"

    # 3. Verb
    is_voiceover = bool(line.get("is_voiceover"))
    delivery_id = line.get("delivery", "none").lower()
    deliveries_data = get_deliveries()
    delivery_info = deliveries_data.get(delivery_id, {"verb": "says", "manner": None})

    if is_voiceover:
        verb = "says in an off-screen voiceover"
    else:
        verb = delivery_info.get("verb", "says")

    # 4. Voice phrase
    # Check if speaker has audio_reference_id
    audio_ref_id = spk1.get("audio_reference_id")
    if audio_ref_id and audio_ref_id in references_by_id:
        audio_ref = references_by_id[audio_ref_id]
        voice_phrase = f"in the voice timbre referenced from <Audio {audio_ref.get('ordinal', 1)}>"
    else:
        # Check library voice or prose
        voice_id = spk1.get("voice_id") or spk1.get("voice_source")
        voices_lib = get_voices()
        if voice_id in voices_lib:
            voice_phrase = voices_lib[voice_id]["paste_phrase"]
        elif spk1.get("voice_prose"):
            prose = spk1["voice_prose"].strip()
            voice_phrase = prose if prose.lower().startswith("in ") else f"in {prose}"
        else:
            # Default fallback to F1/M1
            voice_phrase = voices_lib["M1"]["paste_phrase"]

    # 5. Accent clause
    accent_clause = ""
    accent_raw = (spk1.get("accent") or "").strip()
    if accent_raw:
        accent_clause = f", {accent_raw}"

    # 6. Delivery manner
    manner_clause = ""
    manner = delivery_info.get("manner")
    if manner:
        manner_clause = f", {manner}"

    # 7. Dialogue span
    is_cross_cut = bool(line.get("crosses_cut"))
    is_cutoff = bool(line.get("cutoff"))
    scenetrans_str = "<scenetrans> " if is_cross_cut else ""
    cutoff_str = " <cutoff>" if is_cutoff else ""

    lang = line.get("language", "English")
    text_raw = line.get("text_raw", "")
    norm_text = normalize_text_raw(text_raw)
    dialogue_span = f"{scenetrans_str}<d>[{lang}] {norm_text}</d>{cutoff_str}"

    # 8. Lip closure sentence
    # Voiceover: while {pronoun} lips remain completely closed.
    # Non-voiceover: He/She/It closes his/her/its lips. (or Both speakers close their lips.)
    closure = ""
    if is_voiceover:
        closure = f" while {pron1} lips remain completely closed."
    else:
        if is_cutoff:
            # Cut off mid-speech; ends with dot
            closure = ""
        else:
            if spk2:
                closure = " Both speakers close their lips."
            else:
                # Pronoun capitalized
                pron_map = {"his": ("He", "his"), "her": ("She", "her"), "its": ("It", "its")}
                subject_cap, poss = pron_map.get(pron1, ("He", "his"))
                closure = f" {subject_cap} closes {poss} lips."

    if is_voiceover:
        # Voiceover appends closure directly to dialogue sentence
        sentence = f"{speaker_ref}{speaker_tag} {verb} {voice_phrase}{accent_clause}{manner_clause}, {dialogue_span}{closure}"
    else:
        # Standard sentence
        sentence = f"{speaker_ref}{speaker_tag} {verb} {voice_phrase}{accent_clause}{manner_clause}, {dialogue_span}.{closure}"

    return " ".join(sentence.split())

def expand_onscreen_text(ost: dict[str, Any]) -> str:
    """Expand {{Tm}} to verbatim \"text_raw\" using straight double quotes (§8.0)."""
    text = ost.get("text_raw", "")
    return f'"{text}"'

def apply_cross_cut_destination_prefixes(prompt_text: str, cross_cut_dest_shot_numbers: set[int]) -> str:
    """
    S-04 Safeguard:
    For destination shot N > 1, place the cross-cut prefix immediately AFTER the cut header:
    '[Shot N] At MM:SS.mmm, the camera cuts to <scenetrans> The audio continues seamlessly across the cut. '
    For destination Shot 1, place at start of shot prose.
    """
    result = prompt_text
    prefix = "<scenetrans> The audio continues seamlessly across the cut. "

    for shot_num in cross_cut_dest_shot_numbers:
        if shot_num == 1:
            m = SHOT1_HEADER_RE.search(result)
            if m and prefix not in result[m.start():m.start() + 150]:
                shot1_header = m.group(0)
                result = result[:m.end()] + prefix + result[m.end():]
        else:
            # Find [Shot N] At ... the camera cuts to
            shot_re = re.compile(rf"(\[Shot {shot_num}\] At \d{{2}}:\d{{2}}\.\d{{3}}, the camera cuts to )")
            m = shot_re.search(result)
            if m and prefix not in result[m.start():m.start() + 150]:
                header = m.group(1)
                result = result[:m.end()] + prefix + result[m.end():]

    return result

def stitch_fallback_prose(
    clip: dict[str, Any],
    planned_shots: list[dict[str, Any]],
    line_stubs_by_shot: dict[int, list[str]],
    tm_stubs_by_shot: dict[int, list[str]],
) -> str:
    """
    S-05 Safeguard: Stitches structured plan shots into fallback prose (§8.1b),
    guaranteeing that ALL {{Lk}} and {{Tm}} placeholders for that shot are preserved.
    """
    pieces: list[str] = []
    style_id = clip.get("style_id", "plain")
    pair = clip.get("plain_style_pair", "Live-action, cinematic")
    styles_data = get_styles()

    if style_id == "plain":
        prefix_shot1 = f"[Shot 1] {pair},"
    else:
        named_style = styles_data["named_styles"].get(style_id)
        prefix_shot1 = named_style["t2va_prefix"] if named_style else f"[Shot 1] {pair},"

    sorted_shots = sorted(planned_shots, key=lambda s: s.get("ordinal", 1))

    for idx, s in enumerate(sorted_shots):
        ord_num = s.get("ordinal", idx + 1)
        start_ms = s.get("start_ms", 0)
        time_str = format_ms_timestamp(start_ms)

        if ord_num == 1:
            shot_header = prefix_shot1
        else:
            shot_header = f"[Shot {ord_num}] At {time_str}, the camera cuts to"

        size = s.get("size", "a medium shot")
        angle = s.get("angle", "at eye level")
        action = s.get("events") or s.get("action_chain") or "the scene unfolds"
        cam_phrase = s.get("camera_move") or s.get("camera_phrase") or "The camera pushes in toward the subject"
        landing = s.get("landing") or ""

        # Gather placeholders belonging to this shot
        lk_stubs = line_stubs_by_shot.get(ord_num, [])
        tm_stubs = tm_stubs_by_shot.get(ord_num, [])
        placeholders_part = " ".join(lk_stubs + tm_stubs)

        shot_parts = [shot_header, size, angle, action, cam_phrase, landing, placeholders_part]
        shot_text = " ".join(p.strip() for p in shot_parts if p.strip())
        if not shot_text.endswith("."):
            shot_text += "."
        pieces.append(shot_text)

    return " ".join(pieces)

def render_prompt_body(
    clip: dict[str, Any],
    body_template: str,
    lines: list[dict[str, Any]],
    onscreen_texts: list[dict[str, Any]],
    subjects: list[dict[str, Any]] = None,
    subject_pictures: list[dict[str, Any]] = None,
    references: list[dict[str, Any]] = None,
    speakers: list[dict[str, Any]] = None,
    planned_shots: list[dict[str, Any]] = None,
    prose_fallback: bool = False,
    summary_text: Optional[str] = None,
    task_types: Optional[list[str]] = None,
    retention_entries: Optional[list[dict[str, Any]]] = None,
) -> tuple[str, dict[str, Any]]:
    """
    Render full prompt body deterministically from template and DB context (§8.0, §8.7).
    Returns (rendered_body, metadata).
    """
    mode = clip.get("mode", "T2VA")
    duration_s = clip.get("duration_s", 5)
    audio_policy = clip.get("audio_policy", "dialogue_only")

    speakers_list = speakers or []
    subjects_list = subjects or []
    references_list = references or []
    lines_list = lines or []
    ost_list = onscreen_texts or []

    speakers_by_id = {s.get("id"): s for s in speakers_list}
    subjects_by_id = {s.get("id"): s for s in subjects_list}
    references_by_id = {r.get("id"): r for r in references_list}

    # 1. Deterministic Speaker Numbers (§9.5)
    speaker_id_to_num = assign_speaker_numbers(lines_list)

    # 2. Build Placeholder Maps
    (
        line_id_to_stub,
        stub_to_line,
        onscreen_id_to_stub,
        stub_to_onscreen,
    ) = build_placeholder_maps(lines_list, ost_list)

    # Map lines and on-screen texts to shots
    line_stubs_by_shot: dict[int, list[str]] = {}
    cross_cut_dest_shot_numbers: set[int] = set()

    for line in lines_list:
        lid = line.get("id")
        stub = line_id_to_stub.get(lid)
        shot_ord = line.get("shot_ordinal") or line.get("shot_id") or 1
        if stub:
            line_stubs_by_shot.setdefault(shot_ord, []).append(stub)
        if line.get("crosses_cut"):
            dest_shot = line.get("dest_shot_ordinal") or (shot_ord + 1)
            cross_cut_dest_shot_numbers.add(dest_shot)

    tm_stubs_by_shot: dict[int, list[str]] = {}
    for ost in ost_list:
        tid = ost.get("id")
        stub = onscreen_id_to_stub.get(tid)
        shot_ord = ost.get("shot_ordinal") or ost.get("shot_id") or 1
        if stub:
            tm_stubs_by_shot.setdefault(shot_ord, []).append(stub)

    # 3. Handle Fallback Prose Stitcher (S-05)
    working_template = body_template
    if prose_fallback and planned_shots:
        working_template = stitch_fallback_prose(
            clip, planned_shots, line_stubs_by_shot, tm_stubs_by_shot
        )

    # 4. Substitute {{Lk}} with 8-part canonical speech sentence
    def _replace_lk(match: re.Match) -> str:
        stub = match.group(0)
        line_dict = stub_to_line.get(stub)
        if not line_dict:
            return stub
        return expand_speech_sentence(
            line_dict,
            mode=mode,
            speaker_id_to_num=speaker_id_to_num,
            speakers_by_id=speakers_by_id,
            subjects_by_id=subjects_by_id,
            references_by_id=references_by_id,
        )

    rendered_text = PLACEHOLDER_LK_RE.sub(_replace_lk, working_template)

    # 5. Substitute {{Tm}} with straight double-quoted raw text
    def _replace_tm(match: re.Match) -> str:
        stub = match.group(0)
        ost_dict = stub_to_onscreen.get(stub)
        if not ost_dict:
            return stub
        return expand_onscreen_text(ost_dict)

    rendered_text = PLACEHOLDER_TM_RE.sub(_replace_tm, rendered_text)

    # 6. Apply Cross-Cut Destination Prefixes (S-04)
    if cross_cut_dest_shot_numbers:
        rendered_text = apply_cross_cut_destination_prefixes(
            rendered_text, cross_cut_dest_shot_numbers
        )

    # 7. Compute actual shot count N
    shot_matches = re.findall(r"\[Shot (\d+)\]", rendered_text)
    shot_count = len(shot_matches) if shot_matches else (len(planned_shots) if planned_shots else 1)

    # 8. Assemble Full Mode Body
    final_body = ""
    if mode == "REF2VA":
        # Build subject_definitions deterministically (S-03)
        subj_defs_str = build_subject_definitions(
            subjects=subjects_list,
            subject_pictures=subject_pictures or [],
            references=references_list,
            speakers=speakers_list,
            speaker_id_to_num=speaker_id_to_num,
        )

        # Style opening before [Shot 1]
        style_id = clip.get("style_id", "plain")
        styles_data = get_styles()
        named_style = styles_data["named_styles"].get(style_id)
        ref_style_line = named_style["ref2va_opening"] if named_style else "The target video is in a modern cinematic feature-film style with motivated low-key lighting, a teal-and-amber color grade, rich contrast, fine film grain, shallow depth of field, and natural proportions."

        # Insert house sentence if dialogue_only (§7.6)
        if audio_policy == "dialogue_only":
            if not ref_style_line.endswith("."):
                ref_style_line += "."
            ref_style_line = f"{ref_style_line} {HOUSE_SENTENCE}"

        # If rendered_text already contains subject_definitions: (e.g. manual draft full text):
        if "subject_definitions:" in rendered_text:
            final_body = rendered_text.strip()
        else:
            # 1. Derive task types if not provided
            active_task_types = task_types or derive_task_types(
                clip, references_list, subject_pictures or [], speakers_list
            )
            task_type_str = " + ".join(active_task_types)

            # 2. Build summary paragraph
            editing_prefix = ""
            if "video editing" in active_task_types:
                video_ords = [r.get("ordinal", 1) for r in references_list if r.get("kind") == "video"]
                k_ord = min(video_ords) if video_ords else 1
                editing_prefix = f"The target video is an edited version of <Video {k_ord}>."

            summary_clean = (summary_text or "").strip()
            summary_clean = re.sub(r"^\[.*?\]\s*", "", summary_clean).strip()
            summary_clean = re.sub(r"^The target video is an edited version of <Video \d+>\.\s*", "", summary_clean).strip()

            if editing_prefix:
                if summary_clean:
                    summary_para = f"{editing_prefix} {summary_clean}"
                else:
                    summary_para = f"{editing_prefix} Modifications applied per instructions."
            else:
                if summary_clean:
                    summary_para = summary_clean
                else:
                    summary_para = "A cinematic sequence matching reference cues."

            summary_section = f"summary:\n[{task_type_str}] {summary_para}"

            # 3. Retention analysis section
            retention_str = build_retention_analysis_section(
                subjects=subjects_list,
                references=references_list,
                subject_pictures=subject_pictures or [],
                planned_shots=planned_shots or [],
                retention_entries=retention_entries,
                task_types=active_task_types,
            )
            retention_section = f"retention_analysis:\n{retention_str}"

            # 4. Detailed description section
            shots_body = rendered_text.strip()
            if shots_body.startswith("detailed_description:"):
                shots_body = shots_body[len("detailed_description:"):].strip()

            # Remove leading style sentence if duplicated in shot prose
            m_style = re.match(r"^(The target video is [^\n]+?\.)\s*", shots_body)
            if m_style:
                shots_body = shots_body[m_style.end():].strip()

            # Ensure each [Shot N] begins on its own line: \n[Shot N]
            shots_body = re.sub(r"(?<!\n)\[Shot (\d+)\]", r"\n[Shot \1]", shots_body).strip()

            detailed_desc_section = f"detailed_description:\n{ref_style_line}\n{shots_body}"

            # 5 & 6. Sound and music sections
            sound_val = "N/A" if audio_policy in {"dialogue_only", "silence"} else (clip.get("custom_soundscape") or "Subtle ambient room tone.")
            music_val = "N/A" if audio_policy in {"dialogue_only", "silence"} else (clip.get("custom_music") or "N/A")

            final_body = (
                f"subject_definitions:\n{subj_defs_str}\n\n"
                f"{summary_section}\n\n"
                f"{retention_section}\n\n"
                f"{detailed_desc_section}\n\n"
                f"overall_soundscape:\n{sound_val}\n\n"
                f"non_diegetic_music:\n{music_val}"
            )
    else:
        # T2VA, I2VA, FL2VA, L2VA
        instr_line = build_instruction_line(mode, shot_count, duration_s)

        # In T2VA/frames, insert house sentence in [Shot 1] (§7.6)
        if audio_policy == "dialogue_only":
            if HOUSE_SENTENCE not in rendered_text:
                m_shot1 = re.search(r"(\[Shot 1\]\s*[^.!?<]+[.!?])", rendered_text)
                if m_shot1:
                    first_sent = m_shot1.group(1)
                    rendered_text = rendered_text.replace(first_sent, f"{first_sent} {HOUSE_SENTENCE}", 1)
                else:
                    m_shot1_fallback = re.search(r"(\[Shot 1\]\s*[^<]+)", rendered_text)
                    if m_shot1_fallback:
                        prefix = m_shot1_fallback.group(1).rstrip()
                        if not prefix.endswith("."):
                            prefix += "."
                        rendered_text = rendered_text.replace(m_shot1_fallback.group(1), f"{prefix} {HOUSE_SENTENCE} ", 1)

        sound_val = "N/A" if audio_policy in {"dialogue_only", "silence"} else (clip.get("custom_soundscape") or "Subtle ambient room tone.")
        music_val = "N/A" if audio_policy in {"dialogue_only", "silence"} else (clip.get("custom_music") or "N/A")

        # One paragraph for description, no raw line breaks
        desc_single_para = " ".join(rendered_text.splitlines()).strip()

        fields_block = (
            f"integrated_multimodal_description: {desc_single_para}\n\n"
            f"overall_soundscape: {sound_val}\n\n"
            f"non_diegetic_music: {music_val}"
        )

        if instr_line:
            final_body = f"{instr_line}\n\n{fields_block}"
        else:
            final_body = fields_block

    char_count = len(final_body)

    metadata = {
        "mode": mode,
        "shot_count": shot_count,
        "char_count": char_count,
        "speaker_id_to_num": speaker_id_to_num,
        "prose_fallback": 1 if prose_fallback else 0,
    }

    return final_body, metadata
