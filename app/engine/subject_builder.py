"""Deterministic REF2VA Subject Definition Builder (§8.3, Appendix A.9, S-03).

Strictly compiled in Python with ZERO LLM calls.
Implements formulas for:
- 0 pictures (text-only)
- 1 picture (identity anchor)
- Multiple pictures (face from Picture M, outfit from Picture P)
- Locations, outfits, props, picture anchors, and voice-timbre references.
"""

from __future__ import annotations
from typing import Any, Optional

PICTURE_ROLE_ORDER = [
    "first_frame",
    "keyframe",
    "last_frame",
    "composition_anchor",
    "framing_reference",
]

ROLE_DISPLAY_NAMES = {
    "composition_anchor": "composition anchor",
    "framing_reference": "framing reference",
    "first_frame": "first frame",
    "keyframe": "keyframe",
    "last_frame": "last frame",
}

def build_subject_definitions(
    subjects: list[dict[str, Any]],
    subject_pictures: list[dict[str, Any]],
    references: list[dict[str, Any]],
    speakers: list[dict[str, Any]] = None,
    speaker_id_to_num: dict[int, int] = None,
) -> str:
    """
    Build the exact subject_definitions section lines per Appendix A.9:
    1. Subjects by ordinal (1..n)
    2. Picture anchor lines by picture ordinal and role order
    3. Audio voice-timbre references by audio ordinal
    """
    lines: list[str] = []

    # Map references by id and ordinal
    ref_by_id = {r.get("id"): r for r in references}
    pics_by_ordinal = {r.get("ordinal"): r for r in references if r.get("kind") == "image"}
    audio_by_ordinal = {r.get("ordinal"): r for r in references if r.get("kind") == "audio"}

    # Map subject pictures by subject_id
    sp_by_subject: dict[int, list[dict[str, Any]]] = {}
    for sp in subject_pictures:
        sid = sp.get("subject_id")
        sp_by_subject.setdefault(sid, []).append(sp)

    # 1. Subjects by ordinal
    sorted_subjects = sorted(subjects, key=lambda s: s.get("ordinal", 0))
    for subj in sorted_subjects:
        sid = subj.get("id")
        ord_num = subj.get("ordinal", 1)
        role = subj.get("role", "person").lower()
        role_phrase = (subj.get("role_phrase") or "").strip().rstrip(",")
        pronoun = (subj.get("pronoun") or "her").lower().strip()
        outfit_noun = (subj.get("outfit_noun") or "outfit").strip().rstrip(",")
        appositive = (subj.get("appositive") or "").strip().strip(",")
        feature_list = (subj.get("feature_list") or "").strip().rstrip(",")

        appositive_clause = f", {appositive}," if appositive else ""

        sp_list = sp_by_subject.get(sid, [])
        # Find linked picture references
        linked_pics: list[tuple[int, str]] = []  # (pic_ordinal, role)
        for sp in sp_list:
            ref = ref_by_id.get(sp.get("reference_id"))
            if ref and ref.get("kind") == "image":
                linked_pics.append((ref.get("ordinal", 1), sp.get("reference_role", "identity_anchor")))

        if role in {"person", "character"}:
            identity_pics = [p[0] for p in linked_pics if p[1] == "identity_anchor"]
            outfit_pics = [p[0] for p in linked_pics if p[1] == "outfit"]

            if not linked_pics:
                # 0 pictures (text-only)
                line = (
                    f"<Subject {ord_num}> is the {role_phrase}{appositive_clause} "
                    f"with {pronoun} appearance, facial features, build, and complete {outfit_noun} "
                    f"defined by text alone."
                )
            elif identity_pics and outfit_pics and identity_pics[0] != outfit_pics[0]:
                # Multiple pictures: Face from M, Outfit from P
                m_ord = min(identity_pics)
                p_ord = min(outfit_pics)
                line = (
                    f"<Subject {ord_num}> is the {role_phrase} with {pronoun} face, hair, and build "
                    f"taken from <Picture {m_ord}>{appositive_clause} and {pronoun} complete {outfit_noun} "
                    f"taken from <Picture {p_ord}>."
                )
            else:
                # 1 picture (standard identity anchor)
                pic_ord = identity_pics[0] if identity_pics else linked_pics[0][0]
                line = (
                    f"<Subject {ord_num}> is the {role_phrase} in <Picture {pic_ord}>{appositive_clause} "
                    f"with {pronoun} face, hair, build, and complete {outfit_noun} "
                    f"taken exactly from the reference."
                )
        elif role == "location":
            if linked_pics:
                pic_ord = linked_pics[0][0]
                line = f"<Subject {ord_num}> is the {role_phrase} in <Picture {pic_ord}>, including its {feature_list} exactly as shown."
            else:
                line = f"<Subject {ord_num}> is the {role_phrase}, including its {feature_list} defined by text alone."
        elif role in {"outfit", "accessory", "jewelry", "footwear", "headwear"}:
            pic_ord = linked_pics[0][0] if linked_pics else 1
            line = f"<Subject {ord_num}> is the {role_phrase} in <Picture {pic_ord}>, with its complete appearance and design taken exactly from the reference."
        elif role in {"prop", "weapon", "vehicle", "furniture", "tool", "device", "instrument"}:
            pic_ord = linked_pics[0][0] if linked_pics else 1
            line = f"<Subject {ord_num}> is the {role_phrase} in <Picture {pic_ord}>, with its shape, material, color, and distinctive details taken exactly from the reference."
        else:
            # Fallback for other subject types
            pic_ord = linked_pics[0][0] if linked_pics else 1
            line = f"<Subject {ord_num}> is the {role_phrase} in <Picture {pic_ord}>, with its details taken exactly from the reference."

        # Clean any accidental double spaces
        line = " ".join(line.split())
        lines.append(line)

    # 2. Picture anchor lines:
    # <Picture N> is the {role} for [Shot X], defining {defines_text}.
    # Sorted by picture ordinal, then role order
    anchor_entries: list[tuple[int, int, str, int, str]] = []  # (pic_ord, role_index, role_name, shot_ord, defines_text)
    for sp in subject_pictures:
        ref = ref_by_id.get(sp.get("reference_id"))
        if ref and ref.get("kind") == "image":
            ref_role = sp.get("reference_role", "")
            if ref_role in PICTURE_ROLE_ORDER:
                pic_ord = ref.get("ordinal", 1)
                role_idx = PICTURE_ROLE_ORDER.index(ref_role)
                shot_ord = sp.get("anchor_shot_ordinal") or 1
                defines_text = (sp.get("defines_text") or "the layout").strip()
                display_role = ROLE_DISPLAY_NAMES.get(ref_role, ref_role)
                anchor_entries.append((pic_ord, role_idx, display_role, shot_ord, defines_text))

    anchor_entries.sort(key=lambda e: (e[0], e[1]))
    for pic_ord, _, display_role, shot_ord, defines_text in anchor_entries:
        line = f"<Picture {pic_ord}> is the {display_role} for [Shot {shot_ord}], defining {defines_text}."
        lines.append(line)

    # 3. Audio voice-timbre references:
    # <Audio N> is the voice-timbre reference for <Subject N> (Sx).
    if speakers and speaker_id_to_num:
        # Group audio references
        audio_entries = []
        for spk in speakers:
            audio_ref_id = spk.get("audio_reference_id")
            if audio_ref_id:
                audio_ref = ref_by_id.get(audio_ref_id)
                if audio_ref and audio_ref.get("kind") == "audio":
                    audio_ord = audio_ref.get("ordinal", 1)
                    spk_num = speaker_id_to_num.get(spk.get("id"), 1)
                    subj_id = spk.get("subject_id")
                    # Find subject ordinal if any
                    subj_ord = None
                    if subj_id:
                        for s in subjects:
                            if s.get("id") == subj_id:
                                subj_ord = s.get("ordinal")
                                break
                    target_label = f"<Subject {subj_ord}>" if subj_ord else spk.get("persona", "the speaker")
                    audio_entries.append((audio_ord, spk_num, target_label))

        audio_entries.sort(key=lambda a: (a[0], a[1]))
        for audio_ord, spk_num, target_label in audio_entries:
            line = f"<Audio {audio_ord}> is the voice-timbre reference for {target_label} (S{spk_num})."
            lines.append(line)

    return "\n".join(lines)
