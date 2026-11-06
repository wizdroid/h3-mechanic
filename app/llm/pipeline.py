"""Multi-Stage Pipeline Runner and Progress Streamer (§5.5, §5.6, §8.0–§8.7).

Executes:
- Mode pipeline stages in strict order
- NDJSON streaming events (application/x-ndjson)
- Structural failure retry (max 1 retry with temp +0.1 and seed + 1)
- Fallback prose stitching when prose model fails (T2VA/frames)
- Deterministic subject definitions and rendering
- Preflight fixer loop
- Hard call budget caps: <= 6 for T2VA/frames, <= 8 for REF2VA
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import json
import logging
import random
import sqlite3
import time
from typing import Any, AsyncGenerator, Optional
import uuid

from app.storage.db import get_connection
from app.llm.client import OllamaClient, SchemaValidationError, ModelTruncatedError
from app.llm.prompt_bank import (
    PLAN_JSON_SCHEMA,
    RETENTION_REASONS_SCHEMA,
    SEED_ELABORATION_PROMPT,
    FRAME_ACTION_PROMPT,
    PROSE_WRITER_PROMPT,
    SHOT_WRITER_PROMPT,
    SUMMARY_WRITER_PROMPT,
    RETENTION_WRITER_PROMPT,
    calculate_num_predict,
)
from app.engine.placeholders import (
    build_placeholder_maps,
    validate_template_integrity,
)
from app.engine.subject_builder import build_subject_definitions
from app.engine.renderer import (
    render_prompt_body,
    stitch_fallback_prose,
    derive_task_types,
)
from app.validation.registry import default_registry, ValidationContext, Violation
from app.validation.parser import parse_prompt
from app.validation.estimators import format_ms_timestamp
from app.llm.fixer import run_fixer_loop
from app.resources.vocab import get_camera_moves, get_voices, get_styles

logger = logging.getLogger("h3studio.pipeline")

class PipelineCallCounter:
    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self.calls_made = 0

    def record_call(self) -> None:
        self.calls_made += 1
        if self.calls_made > self.max_calls:
            raise RuntimeError(
                f"Worst-case LLM call budget exceeded: {self.calls_made} calls > max {self.max_calls}"
            )

async def run_stage_with_single_retry(
    client: OllamaClient,
    model: str,
    prompt: str,
    stage_id: str,
    format: Optional[Any],
    options: dict[str, Any],
    call_counter: PipelineCallCounter,
    on_retry_callback: Optional[Any] = None,
) -> tuple[Any, int, int]:
    """
    Execute an LLM stage with at most ONE retry on structural failure (§5.5).
    Retry bumps temperature by +0.1 and perturbs seed by (seed + 1) mod 4294967296.
    Returns (response, attempts_used, elapsed_ms).
    """
    curr_opts = dict(options)
    start_time = time.time()
    last_err: Optional[Exception] = None

    for attempt in range(1, 3):
        call_counter.record_call()
        try:
            resp = await client.generate(
                model=model,
                prompt=prompt,
                format=format,
                options=curr_opts,
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            return resp, attempt, elapsed_ms
        except (SchemaValidationError, ModelTruncatedError, json.JSONDecodeError) as e:
            last_err = e
            if attempt == 1:
                logger.warning("Stage '%s' failed attempt 1 (%s); retrying with temperature +0.1", stage_id, str(e))
                curr_opts["temperature"] = curr_opts.get("temperature", 0.2) + 0.1
                curr_opts["seed"] = (curr_opts.get("seed", 42) + 1) % 4294967296
                if on_retry_callback:
                    await on_retry_callback(stage_id, 2, str(e))
            else:
                raise last_err

    elapsed_ms = int((time.time() - start_time) * 1000)
    raise last_err or RuntimeError(f"Stage {stage_id} failed after {attempt} attempts")

async def execute_generation_pipeline(
    clip_id: int,
    client: OllamaClient,
    drafter_model: str,
    seed_override: Optional[int] = None,
    num_ctx: int = 8192,
) -> AsyncGenerator[str, None]:
    """
    Execute full generation pipeline streaming NDJSON progress events (§5.5, §5.6).
    """
    start_all_time = time.time()
    generation_id = str(uuid.uuid4())
    stage_timings: dict[str, int] = {}

    def _elapsed() -> int:
        return int((time.time() - start_all_time) * 1000)

    # 1. Load clip context from database
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM clips WHERE id = ?", (clip_id,))
        clip_row = cur.fetchone()
        if not clip_row:
            yield json.dumps({"event": "error", "error": {"code": "not_found", "message": f"Clip {clip_id} not found"}}) + "\n"
            return
        clip = dict(clip_row)
        if "video_model" not in clip and "h3_model" in clip:
            clip["video_model"] = clip["h3_model"]
        if "style" not in clip and "style_id" in clip:
            clip["style"] = clip["style_id"]

        cur.execute("SELECT * FROM dialogue_lines WHERE clip_id = ? ORDER BY line_order ASC", (clip_id,))
        lines = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM speakers WHERE clip_id = ?", (clip_id,))
        speakers = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM subjects WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        subjects = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM references_tokens WHERE clip_id = ? ORDER BY position ASC", (clip_id,))
        references = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM onscreen_texts WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        onscreen_texts = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM shots WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
        shots = [dict(r) for r in cur.fetchall()]
        cur.execute("""
            SELECT sp.*, COALESCE(sh.ordinal, 1) as anchor_shot_ordinal
            FROM subject_pictures sp
            JOIN subjects s ON sp.subject_id = s.id
            LEFT JOIN shots sh ON sp.anchor_shot_id = sh.id
            WHERE s.clip_id = ?
        """, (clip_id,))
        subject_pictures = [dict(r) for r in cur.fetchall()]

    mode = clip.get("mode", "T2VA")
    duration_s = clip.get("duration_s", 5)
    audio_policy = clip.get("audio_policy", "dialogue_only")
    seed = seed_override if seed_override is not None else random.randint(0, 4294967295)

    # Budget caps (§5.5, A-32): <= 6 for T2VA/frames, <= 8 for REF2VA
    max_budget = 8 if mode == "REF2VA" else 6
    call_counter = PipelineCallCounter(max_budget)

    # Stage 0 Input Validation (§5.5)
    # Check basic inputs before generating
    ctx_initial = ValidationContext(
        clip=clip,
        parsed_prompt=parse_prompt(""),
        lines=lines,
        speakers=speakers,
        subjects=subjects,
        subject_pictures=subject_pictures,
        references=references,
        shots=shots,
    )
    input_rule_ids = {"PF-11", "PF-13", "PF-20", "PF-31"}
    initial_violations = []
    for r in default_registry.list_rules():
        if r.rule_id in input_rule_ids:
            initial_violations.extend(r.validate(ctx_initial))

    blocking_stage0 = [v for v in initial_violations if v.blocking]
    if blocking_stage0:
        yield json.dumps({
            "event": "error",
            "error": {
                "code": "stage_0",
                "message": f"Stage 0 input validation failed with {len(blocking_stage0)} blocking errors.",
                "violations": [v.to_dict() for v in blocking_stage0],
            }
        }) + "\n"
        return

    # Prepare placeholder maps
    l_map, stub_to_line, t_map, stub_to_t = build_placeholder_maps(lines, onscreen_texts)
    line_stubs_str = ", ".join(l_map.values()) if l_map else "none"

    cam_data = get_camera_moves()
    cam_verbs_str = ", ".join(cam_data.get("camera_patterns", [])[:10])
    voices_data = get_voices()
    voice_ids_str = ", ".join(voices_data.keys())

    prose_fallback_used = False
    working_plan: Optional[dict[str, Any]] = None
    body_template = ""
    summary_text_for_render: Optional[str] = None
    task_types_for_render: Optional[list[str]] = None
    retention_entries_for_render: Optional[list[dict[str, Any]]] = None

    async def _emit_retry(stg: str, attempt: int, err: str) -> None:
        yield json.dumps({
            "event": "stage_retry",
            "stage": stg,
            "attempt": attempt,
            "error": err,
            "ms": _elapsed(),
        }) + "\n"

    try:
        if mode == "T2VA":
            # Stage 1: seed_elaboration
            yield json.dumps({"event": "stage_start", "stage": "seed_elaboration", "ms": _elapsed()}) + "\n"
            style_prefix = clip.get("plain_style_pair", "Live-action, cinematic")
            seed_prompt = SEED_ELABORATION_PROMPT.format(
                seed=clip.get("seed_text", "A dramatic cinematic sequence"),
                duration_s=duration_s,
                ratio=clip.get("ratio", "16:9"),
                style_opening=style_prefix,
                line_stubs=line_stubs_str,
                voice_ids=voice_ids_str,
                shot_budget=f"{duration_s}s duration",
                verbs=cam_verbs_str,
            )

            num_predict_plan = calculate_num_predict("seed_elaboration", {})
            plan_resp, _, t_ms = await run_stage_with_single_retry(
                client=client,
                model=drafter_model,
                prompt=seed_prompt,
                stage_id="seed_elaboration",
                format=PLAN_JSON_SCHEMA,
                options={"temperature": 0.2, "seed": seed, "num_ctx": num_ctx, "num_predict": num_predict_plan},
                call_counter=call_counter,
            )
            stage_timings["seed_elaboration"] = t_ms
            working_plan = plan_resp.parsed_json
            yield json.dumps({"event": "stage_done", "stage": "seed_elaboration", "ms": _elapsed(), "shots_count": len(working_plan.get("shots", []))}) + "\n"

            # Stage 2: prose_writer
            yield json.dumps({"event": "stage_start", "stage": "prose_writer", "ms": _elapsed()}) + "\n"
            word_target = 110 if duration_s <= 6 else (180 if duration_s <= 10 else 260)
            sample_ph = list(l_map.values())[0] if l_map else "{{L1}}"
            prose_prompt = PROSE_WRITER_PROMPT.format(
                plan_json=json.dumps(working_plan),
                style_opening=style_prefix,
                cut_time_n="00:03.000",
                sample_placeholder=sample_ph,
                mode_path_rule="",
                word_target=word_target,
            )

            num_predict_prose = calculate_num_predict("prose_writer", {"word_target": word_target})
            try:
                prose_resp, _, p_ms = await run_stage_with_single_retry(
                    client=client,
                    model=drafter_model,
                    prompt=prose_prompt,
                    stage_id="prose_writer",
                    format=None,
                    options={"temperature": 0.3, "seed": seed, "num_ctx": num_ctx, "num_predict": num_predict_prose},
                    call_counter=call_counter,
                )
                stage_timings["prose_writer"] = p_ms
                body_template = prose_resp.response_text.strip()
                yield json.dumps({"event": "stage_done", "stage": "prose_writer", "ms": _elapsed()}) + "\n"
            except Exception as e:
                # S-05 Safeguard: Fallback prose stitcher (§8.1b)
                logger.warning("prose_writer failed after retries; executing fallback prose stitcher: %s", str(e))
                prose_fallback_used = True
                shots_for_fallback = working_plan.get("shots", [])
                line_stubs_by_shot: dict[int, list[str]] = {}
                assigned_stubs = set()
                for idx, s in enumerate(shots_for_fallback):
                    shot_ord = s.get("ordinal", idx + 1)
                    s["ordinal"] = shot_ord
                    s_line_ids = s.get("line_ids", [])
                    stubs_for_this_shot = []
                    for lid in s_line_ids:
                        lid_str = str(lid).strip()
                        for l_id_key, stub_val in l_map.items():
                            if lid_str in (str(l_id_key), stub_val, stub_val.replace("{", "").replace("}", ""), f"L{l_id_key}"):
                                if stub_val not in stubs_for_this_shot:
                                    stubs_for_this_shot.append(stub_val)
                                    assigned_stubs.add(stub_val)
                    line_stubs_by_shot[shot_ord] = stubs_for_this_shot

                # S-05: Ensure any unassigned dialogue lines are placed into Shot 1 without loss
                for stub_val in l_map.values():
                    if stub_val not in assigned_stubs:
                        line_stubs_by_shot.setdefault(1, []).append(stub_val)
                        assigned_stubs.add(stub_val)

                tm_stubs_by_shot = {1: list(t_map.values())} if t_map else {}
                body_template = stitch_fallback_prose(clip, shots_for_fallback, line_stubs_by_shot, tm_stubs_by_shot)
                yield json.dumps({"event": "stage_done", "stage": "prose_writer", "fallback": True, "ms": _elapsed()}) + "\n"

        elif mode in {"I2VA", "FL2VA", "L2VA"}:
            # Stage 1: frame_action_elaboration
            yield json.dumps({"event": "stage_start", "stage": "frame_action_elaboration", "ms": _elapsed()}) + "\n"
            style_prefix = clip.get("plain_style_pair", "Live-action, cinematic")
            frame_prompt = FRAME_ACTION_PROMPT.format(
                mode=mode,
                frames=f"{len(references)} frame reference(s)",
                action=clip.get("action_text", "A subtle motion sequence"),
                duration_s=duration_s,
                style_opening=style_prefix,
                line_stubs=line_stubs_str,
                shot_count=clip.get("requested_shot_count") or (1 if mode == "FL2VA" else 2),
                verbs=cam_verbs_str,
            )

            num_predict_fa = calculate_num_predict("frame_action_elaboration", {})
            fa_resp, _, t_ms = await run_stage_with_single_retry(
                client=client,
                model=drafter_model,
                prompt=frame_prompt,
                stage_id="frame_action_elaboration",
                format=PLAN_JSON_SCHEMA,
                options={"temperature": 0.2, "seed": seed, "num_ctx": num_ctx, "num_predict": num_predict_fa},
                call_counter=call_counter,
            )
            stage_timings["frame_action_elaboration"] = t_ms
            working_plan = fa_resp.parsed_json
            yield json.dumps({"event": "stage_done", "stage": "frame_action_elaboration", "ms": _elapsed()}) + "\n"

            # Stage 2: prose_writer
            yield json.dumps({"event": "stage_start", "stage": "prose_writer", "ms": _elapsed()}) + "\n"
            word_target = 110 if duration_s <= 6 else (180 if duration_s <= 10 else 260)
            sample_ph = list(l_map.values())[0] if l_map else "{{L1}}"
            prose_prompt = PROSE_WRITER_PROMPT.format(
                plan_json=json.dumps(working_plan),
                style_opening=style_prefix,
                cut_time_n="00:03.000",
                sample_placeholder=sample_ph,
                mode_path_rule=f"Motion for {mode}",
                word_target=word_target,
            )

            num_predict_prose = calculate_num_predict("prose_writer", {"word_target": word_target})
            try:
                prose_resp, _, p_ms = await run_stage_with_single_retry(
                    client=client,
                    model=drafter_model,
                    prompt=prose_prompt,
                    stage_id="prose_writer",
                    format=None,
                    options={"temperature": 0.3, "seed": seed, "num_ctx": num_ctx, "num_predict": num_predict_prose},
                    call_counter=call_counter,
                )
                stage_timings["prose_writer"] = p_ms
                body_template = prose_resp.response_text.strip()
                yield json.dumps({"event": "stage_done", "stage": "prose_writer", "ms": _elapsed()}) + "\n"
            except Exception as e:
                logger.warning("prose_writer failed after retries for %s; executing fallback prose stitcher: %s", mode, str(e))
                prose_fallback_used = True
                shots_for_fallback = working_plan.get("shots", [])
                line_stubs_by_shot: dict[int, list[str]] = {}
                assigned_stubs = set()
                for idx, s in enumerate(shots_for_fallback):
                    shot_ord = s.get("ordinal", idx + 1)
                    s["ordinal"] = shot_ord
                    s_line_ids = s.get("line_ids", [])
                    stubs_for_this_shot = []
                    for lid in s_line_ids:
                        lid_str = str(lid).strip()
                        for l_id_key, stub_val in l_map.items():
                            if lid_str in (str(l_id_key), stub_val, stub_val.replace("{", "").replace("}", ""), f"L{l_id_key}"):
                                if stub_val not in stubs_for_this_shot:
                                    stubs_for_this_shot.append(stub_val)
                                    assigned_stubs.add(stub_val)
                    line_stubs_by_shot[shot_ord] = stubs_for_this_shot

                # S-05: Ensure any unassigned dialogue lines are placed into Shot 1 without loss
                for stub_val in l_map.values():
                    if stub_val not in assigned_stubs:
                        line_stubs_by_shot.setdefault(1, []).append(stub_val)
                        assigned_stubs.add(stub_val)

                tm_stubs_by_shot = {1: list(t_map.values())} if t_map else {}
                body_template = stitch_fallback_prose(clip, shots_for_fallback, line_stubs_by_shot, tm_stubs_by_shot)
                yield json.dumps({"event": "stage_done", "stage": "prose_writer", "fallback": True, "ms": _elapsed()}) + "\n"

        elif mode == "REF2VA":
            # REF2VA has 3 LLM stages: shot_writer, summary_writer, retention_writer (subject_defs is deterministic!)
            # Stage 1: shot_writer
            yield json.dumps({"event": "stage_start", "stage": "shot_writer", "ms": _elapsed()}) + "\n"
            style_id = clip.get("style_id", "plain")
            styles_data = get_styles()
            style_opening = styles_data["named_styles"].get(style_id, {}).get("ref2va_opening", "The target video is in a modern cinematic feature-film style.")
            sample_ph = list(l_map.values())[0] if l_map else "{{L1}}"
            audio_policy_line = "The audio contains only spoken dialogue and direct acoustic Foley." if audio_policy == "dialogue_only" else ""

            # Derive task types for summary writer and retention
            derived_task_types = derive_task_types(clip, references, subject_pictures, speakers)

            # Build detailed shot plan string describing each shot's timing, framing, camera move, and user events
            shot_plan_items = []
            for s in shots:
                s_ord = s.get("ordinal", 1)
                s_start = format_ms_timestamp(s.get("start_ms", 0))
                s_size = s.get("size", "a medium shot")
                s_angle = s.get("angle", "at eye level")
                s_cam = s.get("camera_move") or s.get("camera_phrase") or "The camera holds a static shot"
                s_events = (s.get("events") or "").strip()
                event_desc = f" | Action / Events: {s_events}" if s_events else ""

                # Include dialogue stubs assigned to this shot
                assigned_line_stubs = []
                for l_id_key, stub_val in l_map.items():
                    matching_lines = [l for l in lines if l.get("id") == l_id_key and (l.get("shot_ordinal") == s_ord or l.get("shot_id") == s.get("id"))]
                    if matching_lines:
                        assigned_line_stubs.append(stub_val)
                lines_desc = f" | Dialogue: {', '.join(assigned_line_stubs)}" if assigned_line_stubs else ""

                shot_plan_items.append(f"[Shot {s_ord}] ({s_start}, {s_size}, {s_angle}, Camera: {s_cam}{event_desc}{lines_desc})")

            plan_str = "\n".join(shot_plan_items) if shot_plan_items else f"Clip with {len(shots)} planned shots"

            shot_prompt = SHOT_WRITER_PROMPT.format(
                plan=plan_str,
                style_opening=style_opening,
                cut_time_n="00:03.000",
                sample_placeholder=sample_ph,
                audio_policy_line=audio_policy_line,
                word_target=400,
            )
            num_predict_sw = calculate_num_predict("shot_writer", {})
            try:
                sw_resp, _, sw_ms = await run_stage_with_single_retry(
                    client=client,
                    model=drafter_model,
                    prompt=shot_prompt,
                    stage_id="shot_writer",
                    format=None,
                    options={"temperature": 0.3, "seed": seed, "num_ctx": num_ctx, "num_predict": num_predict_sw},
                    call_counter=call_counter,
                )
                stage_timings["shot_writer"] = sw_ms
                body_template = sw_resp.response_text.strip()
                yield json.dumps({"event": "stage_done", "stage": "shot_writer", "ms": _elapsed()}) + "\n"
            except Exception as e:
                logger.warning("shot_writer failed after retries for REF2VA; executing fallback prose stitcher: %s", str(e))
                prose_fallback_used = True
                line_stubs_by_shot: dict[int, list[str]] = {}
                assigned_stubs = set()
                for idx, s in enumerate(shots):
                    shot_ord = s.get("ordinal", idx + 1)
                    s["ordinal"] = shot_ord
                    stubs_for_this_shot = []
                    for l_id_key, stub_val in l_map.items():
                        matching_lines = [l for l in lines if l.get("id") == l_id_key and (l.get("shot_ordinal") == shot_ord or l.get("shot_id") == s.get("id"))]
                        if matching_lines and stub_val not in stubs_for_this_shot:
                            stubs_for_this_shot.append(stub_val)
                            assigned_stubs.add(stub_val)
                    line_stubs_by_shot[shot_ord] = stubs_for_this_shot

                for stub_val in l_map.values():
                    if stub_val not in assigned_stubs:
                        line_stubs_by_shot.setdefault(1, []).append(stub_val)
                        assigned_stubs.add(stub_val)

                tm_stubs_by_shot = {1: list(t_map.values())} if t_map else {}
                body_template = stitch_fallback_prose(clip, shots, line_stubs_by_shot, tm_stubs_by_shot)
                yield json.dumps({"event": "stage_done", "stage": "shot_writer", "fallback": True, "ms": _elapsed()}) + "\n"

            # Stage 2: summary_writer
            yield json.dumps({"event": "stage_start", "stage": "summary_writer", "ms": _elapsed()}) + "\n"
            task_type_str = " + ".join(derived_task_types)
            sum_prompt = SUMMARY_WRITER_PROMPT.format(
                plan=f"Clip with {len(shots)} shots",
                task_type=task_type_str,
                subject_labels=", ".join(f"<Subject {s.get('ordinal', 1)}>" for s in subjects) or "<Subject 1>",
            )
            num_predict_sum = calculate_num_predict("summary_writer", {})
            summary_text = ""
            try:
                sum_resp, _, sum_ms = await run_stage_with_single_retry(
                    client=client,
                    model=drafter_model,
                    prompt=sum_prompt,
                    stage_id="summary_writer",
                    format=None,
                    options={"temperature": 0.2, "seed": seed, "num_ctx": num_ctx, "num_predict": num_predict_sum},
                    call_counter=call_counter,
                )
                stage_timings["summary_writer"] = sum_ms
                summary_text = sum_resp.response_text.strip()
                yield json.dumps({"event": "stage_done", "stage": "summary_writer", "ms": _elapsed()}) + "\n"
            except Exception as e:
                logger.warning("summary_writer failed: %s; using deterministic fallback", str(e))
                summary_text = "A cinematic sequence matching reference cues."
                yield json.dumps({"event": "stage_done", "stage": "summary_writer", "fallback": True, "ms": _elapsed()}) + "\n"

            # Stage 3: retention_writer (check SQLite retention_markers for empty reasons)
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM retention_markers WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
                retention_rows = [dict(r) for r in cur.fetchall()]

            # If no retention rows exist yet, auto-sync them
            if not retention_rows:
                from app.api.ref2va_routes import sync_retention_entries
                retention_rows = sync_retention_entries(clip_id)

            empty_reason_rows = [r for r in retention_rows if not (r.get("reason") or "").strip()]
            if empty_reason_rows:
                yield json.dumps({"event": "stage_start", "stage": "retention_writer", "ms": _elapsed()}) + "\n"
                items_desc = []
                for r in empty_reason_rows:
                    if r.get("subject_id"):
                        items_desc.append(f"Subject row #{r.get('ordinal')}")
                    else:
                        items_desc.append(f"Reference row #{r.get('ordinal')}")
                ret_prompt = RETENTION_WRITER_PROMPT.format(
                    plan=f"Clip with {len(shots)} shots and {len(retention_rows)} retention items",
                    items_to_justify=", ".join(items_desc),
                )
                num_predict_ret = calculate_num_predict("retention_writer", {"empty_reason_count": len(empty_reason_rows)})
                try:
                    ret_resp, _, ret_ms = await run_stage_with_single_retry(
                        client=client,
                        model=drafter_model,
                        prompt=ret_prompt,
                        stage_id="retention_writer",
                        format=RETENTION_REASONS_SCHEMA,
                        options={"temperature": 0.2, "seed": seed, "num_ctx": num_ctx, "num_predict": num_predict_ret},
                        call_counter=call_counter,
                    )
                    stage_timings["retention_writer"] = ret_ms
                    reasons = ret_resp.parsed_json.get("reasons", [])
                    with get_connection() as conn:
                        cur = conn.cursor()
                        for r_idx, empty_row in enumerate(empty_reason_rows):
                            if r_idx < len(reasons):
                                r_text = reasons[r_idx].strip()
                                cur.execute("UPDATE retention_markers SET reason = ? WHERE id = ?", (r_text, empty_row["id"]))
                        conn.commit()
                        cur.execute("SELECT * FROM retention_markers WHERE clip_id = ? ORDER BY ordinal ASC", (clip_id,))
                        retention_rows = [dict(r) for r in cur.fetchall()]
                    yield json.dumps({"event": "stage_done", "stage": "retention_writer", "ms": _elapsed()}) + "\n"
                except Exception as e:
                    logger.warning("retention_writer failed: %s; keeping default reasons", str(e))
                    yield json.dumps({"event": "stage_done", "stage": "retention_writer", "fallback": True, "ms": _elapsed()}) + "\n"

            retention_entries_for_render = retention_rows
            task_types_for_render = derived_task_types
            summary_text_for_render = summary_text

        # 3. Deterministic Assembler & Renderer (§8.0, §8.7)
        rendered_body, render_meta = render_prompt_body(
            clip=clip,
            body_template=body_template,
            lines=lines,
            onscreen_texts=onscreen_texts,
            subjects=subjects,
            subject_pictures=subject_pictures,
            references=references,
            speakers=speakers,
            planned_shots=working_plan.get("shots") if working_plan else shots,
            prose_fallback=prose_fallback_used,
            summary_text=summary_text_for_render if mode == "REF2VA" else None,
            task_types=task_types_for_render if mode == "REF2VA" else None,
            retention_entries=retention_entries_for_render if mode == "REF2VA" else None,
        )

        # 4. Preflight Validation
        ctx_rendered = ValidationContext(
            clip=clip,
            parsed_prompt=parse_prompt(rendered_body),
            lines=lines,
            speakers=speakers,
            subjects=subjects,
            subject_pictures=subject_pictures,
            references=references,
            shots=shots,
        )
        violations = default_registry.validate_all(ctx_rendered)
        blocking_violations = [v for v in violations if v.blocking]

        yield json.dumps({
            "event": "violations",
            "count": len(violations),
            "blocking": len(blocking_violations),
            "violations": [v.to_dict() for v in violations],
            "ms": _elapsed(),
        }) + "\n"

        # 5. Fixer Loop (if blocking fixable violations exist)
        fixer_retries_used = 0
        if blocking_violations and all(v.fixable for v in blocking_violations):
            yield json.dumps({"event": "stage_start", "stage": "preflight_fixer", "ms": _elapsed()}) + "\n"
            fixed_body, new_violations, fixer_retries_used = await run_fixer_loop(
                ctx=ctx_rendered,
                client=client,
                model=drafter_model,
                max_retries=2,
                seed=seed,
                num_ctx=num_ctx,
            )
            rendered_body = fixed_body
            violations = new_violations
            blocking_violations = [v for v in violations if v.blocking]
            yield json.dumps({"event": "stage_done", "stage": "preflight_fixer", "retries": fixer_retries_used, "ms": _elapsed()}) + "\n"

        # 6. Save prompt record to SQLite
        now_iso = datetime.now(timezone.utc).isoformat()
        char_count = len(rendered_body)
        preflight_json = json.dumps([v.to_dict() for v in violations])
        payload_json = json.dumps(working_plan) if working_plan else "{}"

        final_clip_status = "blocked" if blocking_violations else ("fixed" if fixer_retries_used > 0 else "preflight")

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO prompts (
                    clip_id, generation_id, stage, inputs_revision, body_template,
                    body, char_count, structured_payload_json, preflight_json,
                    overrides_json, fixer_retries, drafter_model, ollama_seed,
                    stage_timings_json, prose_fallback, created_at
                ) VALUES (?, ?, 'draft', ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, ?, ?, ?)
            """, (
                clip_id,
                generation_id,
                clip.get("inputs_revision", 1),
                body_template,
                rendered_body,
                char_count,
                payload_json,
                preflight_json,
                fixer_retries_used,
                drafter_model,
                seed,
                json.dumps(stage_timings),
                1 if prose_fallback_used else 0,
                now_iso,
            ))
            prompt_id = cur.lastrowid

            cur.execute("""
                UPDATE clips
                SET selected_prompt_id = ?, status = ?, updated_at = ?
                WHERE id = ?
            """, (prompt_id, final_clip_status, now_iso, clip_id))
            conn.commit()

        yield json.dumps({
            "event": "done",
            "prompt_id": prompt_id,
            "char_count": char_count,
            "status": final_clip_status,
            "ms": _elapsed(),
        }) + "\n"

    except Exception as e:
        logger.error("Generation pipeline failed for clip %d: %s", clip_id, str(e), exc_info=True)
        # Update clip status to failed
        with get_connection() as conn:
            conn.execute("UPDATE clips SET status = 'failed' WHERE id = ?", (clip_id,))
            conn.commit()
        yield json.dumps({
            "event": "error",
            "error": {
                "code": "pipeline_failure",
                "message": str(e),
            },
            "ms": _elapsed(),
        }) + "\n"
