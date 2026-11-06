"""Atomic Export Module and Backup Manager (§10.1, §10.2, S-07).

Handles:
- Collision detection on integer NN alone (e.g. clip-1-8s.txt and clip-01-8s.txt collide)
- Safe atomic file writes using temp file + os.link / os.replace
- clip-<NN>-<D>s.txt prompt export
- clip-<NN>-PLATES.txt companion file for REF2VA
- Snapshot backups to data/backups/ pruned to the last 5 per clip
"""

from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any, Optional

from app.config import EXPORTS_DIR, BACKUPS_DIR
from app.storage.db import get_connection
from app.validation.registry import default_registry, ValidationContext, Violation
from app.validation.parser import parse_prompt

CLIP_FILE_RE = re.compile(r"^clip-(\d+)-.*")
ORDERED_PLATE_ROLES = [
    "identity_anchor",
    "outfit",
    "prop",
    "location",
    "composition_anchor",
    "framing_reference",
    "first_frame",
    "keyframe",
    "last_frame",
]

ROLE_PLATE_LABELS = {
    "identity_anchor": "identity anchor",
    "outfit": "outfit",
    "prop": "prop",
    "location": "location",
    "composition_anchor": "composition anchor",
    "framing_reference": "framing reference",
    "first_frame": "first frame",
    "keyframe": "keyframe",
    "last_frame": "last frame",
}

class ExportCollisionError(Exception):
    def __init__(self, clip_number: int, colliding_files: list[str]):
        self.clip_number = clip_number
        self.colliding_files = colliding_files
        msg = f"Clip number {clip_number} collides with existing files: {colliding_files}"
        super().__init__(msg)

class PreflightBlockedError(Exception):
    def __init__(self, violations: list[Violation]):
        self.violations = violations
        blocking_messages = [v.message for v in violations if v.blocking]
        super().__init__(f"Preflight validation failed with {len(blocking_messages)} blocking violations: {blocking_messages}")

def scan_existing_clip_numbers(export_dir: Optional[Path] = None) -> list[tuple[int, str]]:
    """Scan export directory for existing clip-(\\d+)-.* files, returning list of (int_NN, filename)."""
    target_dir = export_dir or EXPORTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    results: list[tuple[int, str]] = []
    for item in target_dir.iterdir():
        if item.is_file():
            m = CLIP_FILE_RE.match(item.name)
            if m:
                results.append((int(m.group(1)), item.name))
    return results

def suggest_next_clip_number(export_dir: Optional[Path] = None) -> int:
    """Auto-suggest next clip number: max(existing_NN) + 1, starting from 1."""
    existing = scan_existing_clip_numbers(export_dir)
    if not existing:
        return 1
    return max(nn for nn, _ in existing) + 1

def check_collision(clip_number: int, export_dir: Optional[Path] = None) -> list[str]:
    """
    S-07 Safeguard: Decision is on integer NN alone!
    Both clip-1-8s.txt and clip-01-8s.txt collide.
    Returns list of colliding filenames.
    """
    existing = scan_existing_clip_numbers(export_dir)
    colliding = [fname for nn, fname in existing if nn == int(clip_number)]
    return sorted(colliding)

def write_atomic_file(target_path: Path, content_str: str, overwrite: bool = False) -> None:
    """
    Perform atomic write using temporary file + os.link / os.replace (§10.1).
    File is UTF-8 encoded with no BOM.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = target_path.parent

    # Create temporary file in same directory
    temp_fd, temp_path_str = tempfile.mkstemp(
        prefix=f".tmp_{target_path.stem}_",
        dir=temp_dir,
        text=True,
    )
    temp_path = Path(temp_path_str)

    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content_str)

        if not overwrite:
            # Atomic creation: os.link fails if target exists
            try:
                os.link(temp_path, target_path)
                temp_path.unlink(missing_ok=True)
            except (FileExistsError, OSError) as e:
                if isinstance(e, FileExistsError) or e.errno == 17:
                    raise FileExistsError(f"Target file already exists: {target_path}")
                # Cross-device link fallback: write using open(..., 'x')
                with open(target_path, "x", encoding="utf-8", newline="\n") as out:
                    out.write(content_str)
                temp_path.unlink(missing_ok=True)
        else:
            # Overwrite allowed: atomic replace
            os.replace(temp_path, target_path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass

def build_plates_content(
    references: list[dict[str, Any]],
    subject_pictures: list[dict[str, Any]] = None,
) -> str:
    """
    Generate clip-<NN>-PLATES.txt for REF2VA (§10.2):
    One line per reference in position order:
    <Label>: <filename-or-MISSING> — <role>: <caption>
    Dash is em dash U+2014.
    """
    sp_by_ref: dict[int, list[str]] = {}
    if subject_pictures:
        for sp in subject_pictures:
            rid = sp.get("reference_id")
            role = sp.get("reference_role")
            if rid and role:
                sp_by_ref.setdefault(rid, []).append(role)

    sorted_refs = sorted(references, key=lambda r: (r.get("position", 0) or 0))
    lines: list[str] = []

    for ref in sorted_refs:
        kind = ref.get("kind", "image")
        ord_num = ref.get("ordinal", 1)
        label = f"<Picture {ord_num}>" if kind == "image" else f"<{kind.capitalize()} {ord_num}>"
        source_file = (ref.get("source_file") or ref.get("plate_filename") or "").strip()
        filename_display = source_file if source_file else "MISSING"

        # Resolve role list
        ref_id = ref.get("id")
        assigned_roles = sp_by_ref.get(ref_id, [])
        role_hint = ref.get("role_hint") or ref.get("role")
        if role_hint and role_hint not in assigned_roles:
            assigned_roles.append(role_hint)

        if assigned_roles:
            ordered = []
            for r in ORDERED_PLATE_ROLES:
                if r in assigned_roles:
                    ordered.append(ROLE_PLATE_LABELS.get(r, r))
            # Include any other roles not in standard list
            for r in assigned_roles:
                if r not in ORDERED_PLATE_ROLES and r not in ordered:
                    ordered.append(r)
            roles_str = ", ".join(ordered) if ordered else "unassigned"
        else:
            roles_str = "unassigned"

        caption = (ref.get("caption") or "").strip()
        # Formatted with em dash U+2014
        plate_line = f"{label}: {filename_display} — {roles_str}: {caption}"
        lines.append(plate_line)

    return "\n".join(lines) + "\n"

def create_json_snapshot(
    clip_id: int,
    snapshot_data: dict[str, Any],
    backup_dir: Optional[Path] = None,
) -> Path:
    """Save full clip state snapshot and prune to last 5 per clip (§10.1)."""
    target_dir = backup_dir or BACKUPS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    ts_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    snapshot_path = target_dir / f"clip-{clip_id}-{ts_str}.json"

    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, indent=2, ensure_ascii=False)

    # Prune snapshots for this clip to retain only last 5
    prune_snapshots(clip_id, target_dir, keep_last=5)
    return snapshot_path

def prune_snapshots(clip_id: int, backup_dir: Optional[Path] = None, keep_last: int = 5) -> None:
    """Retain only the last keep_last snapshots for a given clip_id."""
    target_dir = backup_dir or BACKUPS_DIR
    pattern = re.compile(rf"^clip-{clip_id}-(\d{{14}})\.json$")

    clip_snapshots: list[tuple[str, Path]] = []
    for item in target_dir.iterdir():
        if item.is_file():
            m = pattern.match(item.name)
            if m:
                clip_snapshots.append((m.group(1), item))

    # Sort ascending by timestamp string
    clip_snapshots.sort(key=lambda x: x[0])

    if len(clip_snapshots) > keep_last:
        to_delete = clip_snapshots[:-keep_last]
        for _, path in to_delete:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

def export_clip(
    clip_id: int,
    clip_number: int,
    overwrite: bool = False,
    export_dir: Optional[Path] = None,
    backup_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Execute full clip export workflow (§10.1):
    1. Preflight check
    2. Collision detection on integer NN alone
    3. JSON snapshot to data/backups/
    4. Write prompt file (UTF-8, no BOM, one trailing newline)
    5. Write PLATES file (REF2VA)
    6. Update DB record (exported_filename, exported_at, status='exported')
    7. Prune backups to last 5
    """
    target_export_dir = export_dir or EXPORTS_DIR
    target_backup_dir = backup_dir or BACKUPS_DIR

    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1. Fetch clip and prompt
        cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        clip_row = cur.fetchone()
        if not clip_row:
            raise ValueError(f"Clip {clip_id} not found")
        clip = dict(clip_row)
        if "video_model" not in clip and "h3_model" in clip:
            clip["video_model"] = clip["h3_model"]
        if "style" not in clip and "style_id" in clip:
            clip["style"] = clip["style_id"]

        cur.execute("SELECT * FROM prompts WHERE clip_id = ? ORDER BY id DESC LIMIT 1", (clip_id,))
        prompt_row = cur.fetchone()
        if not prompt_row:
            raise ValueError(f"No prompt generated for clip {clip_id}")
        prompt = dict(prompt_row)

        # Fetch lines, speakers, subjects, references, shots
        cur.execute("SELECT * FROM dialogue_lines WHERE clip_id = ? ORDER BY line_order ASC", (clip_id,))
        lines = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM speakers WHERE clip_id = ?", (clip_id,))
        speakers = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM subjects WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        subjects = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM references_tokens WHERE clip_id = ? ORDER BY position ASC", (clip_id,))
        references = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM shots WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        shots = [dict(r) for r in cur.fetchall()]
        cur.execute("""
            SELECT sp.* FROM subject_pictures sp
            JOIN subjects s ON sp.subject_id = s.id
            WHERE s.clip_id = ?
        """, (clip_id,))
        subject_pictures = [dict(r) for r in cur.fetchall()]

        overrides = {}
        if prompt.get("overrides_json"):
            try:
                raw_ovr = json.loads(prompt["overrides_json"])
                if isinstance(raw_ovr, dict):
                    overrides = raw_ovr
                elif isinstance(raw_ovr, list):
                    for item in raw_ovr:
                        if isinstance(item, dict) and "rule_id" in item:
                            overrides[item["rule_id"]] = item
            except Exception:
                overrides = {}

        parsed_prompt = parse_prompt(prompt["body"])
        ctx = ValidationContext(
            clip=clip,
            parsed_prompt=parsed_prompt,
            prompt=prompt,
            lines=lines,
            speakers=speakers,
            subjects=subjects,
            subject_pictures=subject_pictures,
            references=references,
            shots=shots,
            overrides=overrides,
        )

        # Step 1: Preflight check
        violations = default_registry.validate_all(ctx)
        blocking_violations = [v for v in violations if v.blocking]
        if blocking_violations:
            raise PreflightBlockedError(blocking_violations)

        # Step 2: Collision check on integer NN alone (S-07)
        colliding_files = check_collision(clip_number, target_export_dir)
        duration_s = clip.get("duration_s", 5)
        expected_prompt_fname = f"clip-{clip_number:02d}-{duration_s}s.txt"
        expected_plates_fname = f"clip-{clip_number:02d}-PLATES.txt"

        if colliding_files and not overwrite:
            # If files exist and overwrite is false -> error
            raise ExportCollisionError(clip_number, colliding_files)

        # Step 3: Write JSON snapshot to data/backups/
        snapshot_payload = {
            "clip": clip,
            "prompt": prompt,
            "dialogue_lines": lines,
            "speakers": speakers,
            "subjects": subjects,
            "subject_pictures": subject_pictures,
            "references": references,
            "shots": shots,
            "overrides": overrides,
            "target_filename": expected_prompt_fname,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        snapshot_file = create_json_snapshot(clip_id, snapshot_payload, target_backup_dir)

        # Step 4: Write prompt file atomically
        prompt_target_path = target_export_dir / expected_prompt_fname
        prompt_content = prompt["body"].rstrip("\n") + "\n"

        files_written: list[Path] = []
        try:
            write_atomic_file(prompt_target_path, prompt_content, overwrite=overwrite)
            files_written.append(prompt_target_path)

            # Step 5: Write PLATES file (if REF2VA)
            plates_target_path = None
            if clip.get("mode") == "REF2VA":
                plates_target_path = target_export_dir / expected_plates_fname
                plates_content = build_plates_content(references, subject_pictures)
                write_atomic_file(plates_target_path, plates_content, overwrite=overwrite)
                files_written.append(plates_target_path)

            # Step 6: Update DB
            now_iso = datetime.now(timezone.utc).isoformat()
            cur.execute("""
                UPDATE prompts
                SET exported_filename = ?, exported_at = ?
                WHERE id = ?
            """, (expected_prompt_fname, now_iso, prompt["id"]))

            cur.execute("""
                UPDATE clips
                SET status = 'exported', updated_at = ?
                WHERE id = ?
            """, (now_iso, clip_id))

            conn.commit()
        except Exception:
            conn.rollback()
            # Clean up written files if failed
            for f in files_written:
                f.unlink(missing_ok=True)
            raise

        return {
            "status": "ok",
            "clip_id": clip_id,
            "clip_number": clip_number,
            "prompt_file": str(prompt_target_path),
            "plates_file": str(plates_target_path) if plates_target_path else None,
            "snapshot_file": str(snapshot_file),
            "exported_at": now_iso,
        }
