"""Shared workbook helpers for build-rules and rules-check.

The categorized workbook's rule sheets all use the same five columns; the
`Source references` sheet maps an index to a cheatsheet filename. This module
normalizes rows, resolves sources, and runs the partition check between the
master `Table 1` and the topic sheets.
"""

from __future__ import annotations

from collections import Counter
from typing import List, Tuple

RULES_HEADERS = [
    "Category",
    "Keyword or Element",
    "Snippet or Description Template",
    "Usage Example",
    "Source",
]

SOURCE_SHEET = "Source references"

TOPIC_SHEETS = [
    "Camera Moves",
    "Framing & Lens",
    "Shot Cuts & Editing",
    "Voice Library",
    "Vocal Delivery",
    "Faces & Performance",
    "Dialogue & Languages",
    "Sound & Music",
    "Lighting, Color & Look",
    "Reference Modes",
    "Prompt Structure",
]

MASTER_SHEET = "Table 1"


def rules_sheet_names(sheets) -> List[str]:
    return [n for n in sheets if n != SOURCE_SHEET]


def normalize_row(row: List[str]) -> Tuple[str, ...]:
    """Pad a row to five columns and strip each cell."""
    return tuple((row[i].strip() if i < len(row) else "") for i in range(5))


def source_map(sheets) -> dict[str, str]:
    """Index -> filename from the `Source references` sheet."""
    out: dict[str, str] = {}
    rows = sheets.get(SOURCE_SHEET, [])
    for row in rows[1:]:
        if not row:
            continue
        idx = (row[0] or "").strip()
        ref = (row[1] or "").strip() if len(row) > 1 else ""
        if idx:
            out[idx] = ref
    return out


def resolve_sources(src_cell: str, src_map: dict[str, str]) -> Tuple[List[str], List[str]]:
    """Split a Source cell ("6, 9") into resolved filenames and any unknown indexes."""
    if not src_cell:
        return [], []
    resolved: List[str] = []
    unknown: List[str] = []
    for part in src_cell.replace(",", " ").split():
        part = part.strip()
        if not part:
            continue
        if part in src_map:
            resolved.append(src_map[part])
        else:
            unknown.append(part)
    return resolved, unknown


def partition_errors(sheets) -> List[str]:
    """Return disagreements between `Table 1` and the union of the topic sheets."""
    master = Counter(normalize_row(r) for r in sheets.get(MASTER_SHEET, [])[1:])
    topic = Counter()
    for name in TOPIC_SHEETS:
        for r in sheets.get(name, [])[1:]:
            topic[normalize_row(r)] += 1
    errors: List[str] = []
    for row, n in (master - topic).items():
        errors.append(f"row only in {MASTER_SHEET}: {row[0]!r} / {row[1]!r}")
    for row, n in (topic - master).items():
        errors.append(f"row only in topic sheets (missing from {MASTER_SHEET}): {row[0]!r} / {row[1]!r}")
    return errors
