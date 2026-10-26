"""Minimal stdlib-only .xlsx reader (zip + XML).

An .xlsx file is a ZIP of XML parts. This module extracts, per worksheet, a
list of rows where each row is a list of cell values (strings or numbers),
converting shared strings and inline strings along the way. It is enough to
read the categorized rules workbook without any third-party dependency.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import List

_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _text_of(el: ET.Element) -> str:
    return "".join(t.text or "" for t in el.iter(f"{{{_NS['a']}}}t"))


def _read_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    out: List[str] = []
    for si in root.findall("a:si", _NS):
        out.append(_text_of(si))
    return out


def _cell_value(c: ET.Element, shared: List[str]):
    t = c.get("t")
    v = c.find("a:v", _NS)
    if t == "inlineStr":
        is_el = c.find("a:is", _NS)
        return _text_of(is_el) if is_el is not None else ""
    if v is None:
        return ""
    raw = v.text or ""
    if t == "s":
        idx = int(raw)
        return shared[idx] if 0 <= idx < len(shared) else ""
    if t == "b":
        return "1" if raw == "1" else "0"
    return raw


def read_sheets(path: str | Path) -> dict[str, List[List[str]]]:
    """Return {sheet_name: [ [cell, cell, ...], ... ]} for every worksheet."""
    p = Path(path)
    with zipfile.ZipFile(p) as zf:
        shared = _read_shared_strings(zf)
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid2target = {r.get("Id"): r.get("Target") for r in rels}
        rel_ns = f"{{{_NS['r']}}}id"

        result: dict[str, List[List[str]]] = {}
        for sh in wb.find("a:sheets", _NS).findall("a:sheet", _NS):
            name = sh.get("name")
            rid = sh.get(rel_ns)
            target = rid2target.get(rid, "")
            if not target.startswith("xl/"):
                target = "xl/" + target
            ws_root = ET.fromstring(zf.read(target))
            rows: List[List[str]] = []
            for row in ws_root.iter(f"{{{_NS['a']}}}row"):
                cells: List[str] = []
                for c in row.findall("a:c", _NS):
                    cells.append(_cell_value(c, shared))
                rows.append(cells)
            result[name] = rows
    return result
