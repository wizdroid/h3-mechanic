"""Rebuild rules/rules.json from the categorized workbook.

    python3 app/rules_build.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
ROOT = APP.parent
sys.path.insert(0, str(APP))

import rules_data  # noqa: E402
from xlsx_io import read_sheets  # noqa: E402

WORKBOOK = ROOT / "cheatsheets" / "minimax-h3-cheatsheet-categorized.xlsx"
OUT = ROOT / "rules" / "rules.json"


def build() -> dict:
    sheets = read_sheets(WORKBOOK)
    src_map = rules_data.source_map(sheets)
    errors = []
    out_sheets = {}
    for name in rules_data.rules_sheet_names(sheets):
        rows = []
        for raw in sheets[name][1:]:
            if not raw or not any(cell.strip() for cell in raw):
                continue
            category, keyword, snippet, example, src_cell = rules_data.normalize_row(raw)
            if not category and not keyword and not snippet:
                continue
            resolved, unknown = rules_data.resolve_sources(src_cell, src_map)
            if unknown:
                errors.append(f"{name}: {keyword!r} source index {unknown} does not resolve")
            rows.append({
                "category": category,
                "keyword": keyword,
                "snippet": snippet,
                "example": example,
                "source": resolved,
            })
        out_sheets[name] = rows
    errors.extend(rules_data.partition_errors(sheets))
    if errors:
        raise SystemExit("rules build failed:\n" + "\n".join(errors[:30]))
    return {
        "schemaVersion": 1,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "cheatsheets/minimax-h3-cheatsheet-categorized.xlsx",
        "structure": "sheets.<name> is an ordered list of rows {category, keyword, snippet, example, source}",
        "sources": src_map,
        "sheets": out_sheets,
    }


def main() -> None:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    count = sum(len(v) for v in payload["sheets"].values())
    print(f"ok  {OUT}  {len(payload['sheets'])} sheets  {count} rows")


if __name__ == "__main__":
    main()
