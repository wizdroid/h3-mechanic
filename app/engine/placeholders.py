"""Placeholder Protocol and Template Integrity Validator (§8.0).

Handles:
- Dialogue line stubs ({{Lk}}) and on-screen text stubs ({{Tm}})
- Template placeholder integrity checking before rendering
- Structured plan preparation with zero sensitive text exposure
"""

from __future__ import annotations
import re
from typing import Any, Optional

PLACEHOLDER_LK_RE = re.compile(r"\{\{L(\d+)\}\}")
PLACEHOLDER_TM_RE = re.compile(r"\{\{T(\d+)\}\}")
ANY_PLACEHOLDER_RE = re.compile(r"\{\{([^}]+)\}\}")
SHOT_HEADER_RE = re.compile(r"\[Shot (\d+)\]")

def build_placeholder_maps(
    lines: list[dict[str, Any]],
    onscreen_texts: list[dict[str, Any]],
) -> tuple[dict[int, str], dict[str, dict[str, Any]], dict[int, str], dict[str, dict[str, Any]]]:
    """
    Sort dialogue lines by (shot.start_ms, line_order, id) and assign k = 1..n.
    Sort on-screen texts by ordinal (or id) and assign m = 1..M.

    Returns:
      (line_id_to_stub, stub_to_line, onscreen_id_to_stub, stub_to_onscreen)
    """
    sorted_lines = sorted(
        lines,
        key=lambda l: (
            l.get("shot_start_ms", 0) or 0,
            l.get("line_order", 0) or 0,
            l.get("id", 0) or 0,
        ),
    )

    line_id_to_stub: dict[int, str] = {}
    stub_to_line: dict[str, dict[str, Any]] = {}

    for k, line in enumerate(sorted_lines, start=1):
        stub = f"{{{{L{k}}}}}"
        lid = line.get("id", k)
        line_id_to_stub[lid] = stub
        stub_to_line[stub] = line

    sorted_onscreen = sorted(
        onscreen_texts,
        key=lambda t: (t.get("ordinal", 0) or 0, t.get("id", 0) or 0),
    )

    onscreen_id_to_stub: dict[int, str] = {}
    stub_to_onscreen: dict[str, dict[str, Any]] = {}

    for m, ost in enumerate(sorted_onscreen, start=1):
        ordinal = ost.get("ordinal", m)
        stub = f"{{{{T{ordinal}}}}}"
        tid = ost.get("id", m)
        onscreen_id_to_stub[tid] = stub
        stub_to_onscreen[stub] = ost

    return line_id_to_stub, stub_to_line, onscreen_id_to_stub, stub_to_onscreen

def validate_template_integrity(
    template_text: str,
    mode: str,
    expected_line_stubs: list[str],
    expected_tm_stubs: list[str],
    line_to_shot_ordinal: Optional[dict[str, int]] = None,
) -> list[str]:
    """
    Verify template integrity per §8.0:
    1. Every {{Lk}} appears exactly once, and sequence is strictly increasing.
    2. For REF2VA, {{Lk}} sits in the shot whose id is that line's shot_id.
    3. Every {{Tm}} appears exactly once.
    4. No {{V: tokens.
    5. No leftover {{...}} placeholders.
    """
    errors: list[str] = []

    if "{{V:" in template_text:
        errors.append("Template contains forbidden placeholder prefix '{{V:'.")

    # Extract all {{Lk}} occurrences in order of appearance
    lk_matches = list(PLACEHOLDER_LK_RE.finditer(template_text))
    found_lk_stubs = [m.group(0) for m in lk_matches]
    found_lk_indices = [int(m.group(1)) for m in lk_matches]

    # Verify each expected {{Lk}} appears exactly once
    for stub in expected_line_stubs:
        count = found_lk_stubs.count(stub)
        if count == 0:
            errors.append(f"Missing required dialogue placeholder '{stub}'.")
        elif count > 1:
            errors.append(f"Duplicate dialogue placeholder '{stub}' found {count} times.")

    # Sequence strictly increasing
    for i in range(len(found_lk_indices) - 1):
        if found_lk_indices[i] >= found_lk_indices[i + 1]:
            errors.append(
                f"Dialogue placeholder sequence is not strictly increasing: "
                f"L{found_lk_indices[i]} appears before or at L{found_lk_indices[i + 1]}."
            )

    # In REF2VA, verify {{Lk}} sits inside the owning shot
    if mode == "REF2VA" and line_to_shot_ordinal:
        # Split template by shots
        shot_positions = list(SHOT_HEADER_RE.finditer(template_text))
        for m in lk_matches:
            stub = m.group(0)
            expected_shot_ord = line_to_shot_ordinal.get(stub)
            if expected_shot_ord is not None:
                # Find which shot section contains this match position
                pos = m.start()
                owning_shot_ord = None
                for idx, sp in enumerate(shot_positions):
                    s_ord = int(sp.group(1))
                    next_start = shot_positions[idx + 1].start() if idx + 1 < len(shot_positions) else len(template_text)
                    if sp.start() <= pos < next_start:
                        owning_shot_ord = s_ord
                        break
                if owning_shot_ord is not None and owning_shot_ord != expected_shot_ord:
                    errors.append(
                        f"Dialogue placeholder '{stub}' is placed in [Shot {owning_shot_ord}], "
                        f"but belongs to [Shot {expected_shot_ord}]."
                    )

    # Verify {{Tm}} stubs
    found_tm_stubs = PLACEHOLDER_TM_RE.findall(template_text)
    for stub in expected_tm_stubs:
        m = re.search(r"\d+", stub)
        ord_num = m.group(0) if m else ""
        count = found_tm_stubs.count(ord_num)
        if count == 0:
            errors.append(f"Missing required on-screen text placeholder '{stub}'.")
        elif count > 1:
            errors.append(f"Duplicate on-screen text placeholder '{stub}' found {count} times.")

    # Check for unexpected or leftover placeholders
    all_placeholders = ANY_PLACEHOLDER_RE.findall(template_text)
    for ph in all_placeholders:
        raw = f"{{{{{ph}}}}}"
        if not (PLACEHOLDER_LK_RE.match(raw) or PLACEHOLDER_TM_RE.match(raw)):
            errors.append(f"Unexpected unexpanded placeholder: '{raw}'.")

    return errors
