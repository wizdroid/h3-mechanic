"""Preflight rules PF-01 through PF-13 for all modes (§9.1)."""

from __future__ import annotations
import re
from typing import Any, Optional
from app.validation.registry import BaseRule, ValidationContext, Violation
from app.validation.parser import ParsedPrompt, CUT_TIME_RE
from app.validation.estimators import (
    count_english_words,
    count_sentences,
    estimate_shot_min_duration_ms,
    estimate_line_duration_tenths,
    normalize_text_raw,
    assign_speaker_numbers,
)
from app.resources.vocab import (
    get_shot_budgets,
    get_mood_words,
    get_voices,
    get_deliveries,
    get_scripts,
)

NON_LATIN_SCRIPT_RE = re.compile(r"[\u0900-\u0D7F]")
MARKDOWN_FENCE_RE = re.compile(r"(```|~~~)")
MARKDOWN_BULLET_RE = re.compile(r"^\s*([*\-+]|\d+\.)\s+", re.MULTILINE)

class PF01_TemplateIntegrity(BaseRule):
    rule_id = "PF-01"
    name = "Template and Layout Integrity"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        mode = ctx.clip.get("mode")
        p = ctx.parsed_prompt

        if p.has_carriage_return:
            violations.append(
                self.make_violation(
                    ctx, "raw", "Prompt body must not contain carriage returns (\\r).", suggested_text=p.raw_body.replace("\r", "")
                )
            )
        if p.has_feff:
            violations.append(
                self.make_violation(
                    ctx, "raw", "Prompt body must not contain byte order mark U+FEFF.", suggested_text=p.raw_body.replace("\ufeff", "")
                )
            )
        if p.lines_with_trailing_spaces:
            violations.append(
                self.make_violation(
                    ctx,
                    "raw",
                    f"Lines {p.lines_with_trailing_spaces} have illegal trailing spaces.",
                    suggested_text="\n".join(l.rstrip() for l in p.raw_body.splitlines()),
                )
            )

        if mode == "REF2VA":
            expected_headers = [
                "subject_definitions",
                "summary",
                "retention_analysis",
                "detailed_description",
                "overall_soundscape",
                "non_diegetic_music",
            ]
            for h in expected_headers:
                if h not in p.sections:
                    violations.append(
                        self.make_violation(
                            ctx,
                            h,
                            f"REF2VA prompt missing required section header '{h}:'",
                        )
                    )
        else:
            # T2VA, I2VA, FL2VA, L2VA
            expected_fields = [
                "integrated_multimodal_description",
                "overall_soundscape",
                "non_diegetic_music",
            ]
            for f in expected_fields:
                if f not in p.sections:
                    violations.append(
                        self.make_violation(
                            ctx,
                            f,
                            f"{mode} prompt missing required field '{f}: '",
                        )
                    )
            if mode in {"I2VA", "FL2VA", "L2VA"} and not p.instruction_line:
                violations.append(
                    self.make_violation(
                        ctx,
                        "instruction_line",
                        f"{mode} prompt requires verbatim instruction line from Appendix A.2.",
                    )
                )
            if p.raw_line_breaks_in_desc:
                violations.append(
                    self.make_violation(
                        ctx,
                        "integrated_multimodal_description",
                        f"{mode} integrated_multimodal_description must be a single continuous paragraph without raw line breaks.",
                    )
                )

        return violations

class PF02_ShotTimestamps(BaseRule):
    rule_id = "PF-02"
    name = "Shot Cut Timestamps"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        shots = ctx.parsed_prompt.shots
        duration_s = ctx.clip.get("duration_s", 15)
        max_duration_ms = duration_s * 1000

        prev_time = -1

        for shot in shots:
            if shot.number == 1:
                if shot.cut_wording_type != "shot1" or shot.start_ms is not None:
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            "[Shot 1] must not have a timestamp.",
                            suggested_text="[Shot 1]",
                        )
                    )
            else:
                if shot.cut_wording_type == "shot_cuts_to":
                    # Warning, autofixed to camera cuts to
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            f"[Shot {shot.number}] uses 'the shot cuts to' instead of 'the camera cuts to'.",
                            severity="warning",
                            blocking=False,
                            suggested_text=f"[Shot {shot.number}] At {shot.cut_time_str}, the camera cuts to ",
                        )
                    )
                elif shot.cut_wording_type == "colon_timestamp":
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            f"[Shot {shot.number}] timestamp uses colon separator instead of dot (e.g. MM:SS:mmm).",
                            suggested_text="use MM:SS.mmm",
                        )
                    )
                elif shot.cut_wording_type == "invalid":
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            f"[Shot {shot.number}] header must match 'At MM:SS.mmm, the camera cuts to ' exactly.",
                        )
                    )

                if shot.start_ms is not None:
                    if shot.start_ms <= prev_time:
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] timestamp ({shot.cut_time_str}) is not strictly increasing.",
                            )
                        )
                    if shot.start_ms >= max_duration_ms:
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] timestamp ({shot.cut_time_str}) must be less than clip duration ({duration_s}s).",
                            )
                        )
                    prev_time = shot.start_ms

        return violations

class PF03_ShotBudgets(BaseRule):
    rule_id = "PF-03"
    name = "Shot Budget and Constraints"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        mode = ctx.clip.get("mode")
        duration_s = ctx.clip.get("duration_s", 5)
        req_shots = ctx.clip.get("requested_shot_count")
        shots = ctx.parsed_prompt.shots
        actual_shot_count = len(shots)

        budgets = get_shot_budgets()
        matching_budget = None
        for b in budgets:
            if b["min_duration"] <= duration_s <= b["max_duration"]:
                matching_budget = b
                break

        if matching_budget:
            min_shots = matching_budget["min_shots"]
            max_shots = matching_budget["max_shots"]

            # FL2VA with requested_shot_count == 1 (or 1 shot generated) waives minimum only
            if mode == "FL2VA" and (req_shots == 1 or (req_shots is None and actual_shot_count == 1)):
                min_shots = 1

            if actual_shot_count < min_shots or actual_shot_count > max_shots:
                violations.append(
                    self.make_violation(
                        ctx,
                        "shots",
                        f"Shot count ({actual_shot_count}) outside allowed range [{min_shots}, {max_shots}] for {duration_s}s.",
                    )
                )

            if req_shots is not None and req_shots != actual_shot_count:
                violations.append(
                    self.make_violation(
                        ctx,
                        "shots",
                        f"Generated shot count ({actual_shot_count}) does not match requested_shot_count ({req_shots}).",
                    )
                )

        # Check per-shot minimum durations
        for shot in shots:
            shot_lines = [l for l in ctx.lines if l.get("shot_id") == shot.number or l.get("shot_number") == shot.number]
            min_dur_ms = estimate_shot_min_duration_ms(shot_lines)
            if shot.number < len(shots) and shot.start_ms is not None:
                next_shot = shots[shot.number]
                if next_shot.start_ms is not None:
                    actual_dur_ms = next_shot.start_ms - (shot.start_ms or 0)
                    if actual_dur_ms < min_dur_ms:
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] duration ({actual_dur_ms}ms) is shorter than estimated minimum ({min_dur_ms}ms).",
                            )
                        )

        return violations

class PF04_CameraPhrases(BaseRule):
    rule_id = "PF-04"
    name = "Camera Phrase Precision and Modifiers"
    default_severity = "error"
    basis = "heuristic"
    fixable = True
    overridable = True

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        p = ctx.parsed_prompt

        # Check style line in REF2VA
        if p.style_line:
            from app.validation.parser import _parse_camera_in_text
            hits, _, _, _, _ = _parse_camera_in_text(p.style_line, is_ref_mode=True)
            if hits:
                violations.append(
                    self.make_violation(
                        ctx,
                        "detailed_description",
                        f"The REF2VA style line contains an illegal camera phrase: '{hits[0]}'.",
                    )
                )

        for shot in p.shots:
            if len(shot.camera_hits) == 0:
                violations.append(
                    self.make_violation(
                        ctx,
                        "shots",
                        f"[Shot {shot.number}] contains no official camera phrase from Appendix A.5.",
                    )
                )
            elif len(shot.camera_hits) > 1:
                violations.append(
                    self.make_violation(
                        ctx,
                        "shots",
                        f"[Shot {shot.number}] contains multiple camera phrases ({len(shot.camera_hits)}): {shot.camera_hits}.",
                    )
                )
            else:
                fam = shot.camera_family
                # Landing check
                if fam in {"static", "pov", "shake"}:
                    if not shot.landing:
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] ({fam}) is missing an optional landing clause (warning).",
                                severity="warning",
                                blocking=False,
                            )
                        )
                    # Any modifier on Static, POV, Shake is an error
                    if shot.modifiers:
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] ({fam}) forbids all speed and amplitude modifiers; found {shot.modifiers}.",
                            )
                        )
                else:
                    # Required move needs landing substring
                    if not shot.landing:
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] required camera move needs a landing substring (' toward ', ' revealing ', ' onto ', ' as ').",
                            )
                        )
                    # Modifier check
                    if shot.has_invalid_modifier:
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] has illegal speed or amplitude modifier in {shot.modifiers}.",
                            )
                        )

        return violations

class PF05_FaceHeuristic(BaseRule):
    rule_id = "PF-05"
    name = "Face Safety and Framing Heuristic"
    default_severity = "error"
    basis = "heuristic"
    fixable = True
    overridable = True

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        for shot in ctx.parsed_prompt.shots:
            text_orig = shot.text
            # Remove <d>...</d>
            text_stripped = re.sub(r"<d>.*?</d>", "", text_orig, flags=re.DOTALL)

            exempt_keywords = [
                "from behind",
                "faces not visible",
                "face is not visible",
                "no readable face",
                "extreme wide shot",
                "silhouette",
            ]
            is_exempt = any(kw in text_stripped.lower() for kw in exempt_keywords)

            # POV shot is exempt ONLY when it also contains face(s) not visible
            is_pov = shot.camera_family == "pov" or "point of view" in text_orig.lower()
            if is_pov:
                if not ("face is not visible" in text_stripped.lower() or "faces not visible" in text_stripped.lower()):
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            f"[Shot {shot.number}] POV shot must explicitly state 'face is not visible' or 'faces not visible'.",
                        )
                    )

            if not is_exempt:
                has_dialogue = "</d>" in text_orig
                has_face_size = any(sz in text_stripped.lower() for sz in ["close-up", "medium close-up", "medium shot"])

                if has_dialogue or has_face_size:
                    # Must contain front-facing or three-quarter
                    if not ("front-facing" in text_stripped.lower() or "three-quarter" in text_stripped.lower()):
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] with readable/speaking face must be 'front-facing' or 'three-quarter'.",
                            )
                        )

                    # Observable expression token
                    expression_tokens = [
                        "eye", "eyes", "brow", "brows", "lip", "lips", "mouth", "jaw",
                        "breath", "hand", "hands", "shoulder", "shoulders", "gaze", "tear", "smile"
                    ]
                    if not any(re.search(rf"\b{tok}\b", text_stripped, re.IGNORECASE) for tok in expression_tokens):
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] with readable face lacks physical expression token (eyes, brows, mouth, etc.).",
                            )
                        )

                    # Banned lens / camera phrases on face shots
                    banned_lens = ["24mm", "wide-angle", "fisheye", "ultra-wide", "gopro", "action cam"]
                    for bl in banned_lens:
                        if bl in text_stripped.lower():
                            violations.append(
                                self.make_violation(
                                    ctx,
                                    "shots",
                                    f"[Shot {shot.number}] uses wide-angle/action-cam phrase '{bl}' on a face shot.",
                                )
                            )

                    # Count of front-facing <= 2
                    ff_count = len(re.findall(r"\bfront-facing\b", text_stripped, re.IGNORECASE))
                    if ff_count > 2:
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] 'front-facing' appears {ff_count} times (max 2 allowed).",
                            )
                        )

                    # Banned face count phrases
                    for bfc in ["three faces", "four faces", "many faces"]:
                        if bfc in text_stripped.lower():
                            violations.append(
                                self.make_violation(
                                    ctx,
                                    "shots",
                                    f"[Shot {shot.number}] contains illegal multiple face phrasing '{bfc}'.",
                                )
                            )

            # Mouth closure checks (uses original text)
            # After a non-voiceover </d>, next 80 chars must contain 'lips' unless <cutoff> follows
            d_indices = [m.end() for m in re.finditer(r"</d>", text_orig)]
            for d_end in d_indices:
                after_text = text_orig[d_end:d_end + 80]
                if "<cutoff>" not in text_orig[d_end:d_end + 30]:
                    # Check if voiceover
                    before_text = text_orig[max(0, d_end - 150):d_end]
                    if "voiceover" in before_text.lower():
                        # Voiceover line must contain lips remain completely closed
                        if "lips remain completely closed" not in text_orig:
                            violations.append(
                                self.make_violation(
                                    ctx,
                                    "shots",
                                    f"[Shot {shot.number}] voiceover must state 'lips remain completely closed'.",
                                )
                            )
                    else:
                        if "lips" not in after_text.lower():
                            violations.append(
                                self.make_violation(
                                    ctx,
                                    "shots",
                                    f"[Shot {shot.number}] speaking line must be followed by mouth closure ('lips') within 80 characters.",
                                )
                            )

        return violations

class PF06_SpeechExpansion(BaseRule):
    rule_id = "PF-06"
    name = "Speech Sentence Expansion"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        voices = get_voices()
        deliveries = get_deliveries()

        # Check for bare library ids (F1..F10, M1..M11, K1..K2) in prompt text
        all_text = ctx.parsed_prompt.raw_body
        for vid in voices.keys():
            if re.search(rf"\b{vid}\b", all_text):
                violations.append(
                    self.make_violation(
                        ctx,
                        "shots",
                        f"Prompt contains bare voice library ID '{vid}'. Full paste phrase must be expanded.",
                    )
                )

        # Speaker numbering and consistency
        if ctx.lines and ctx.speakers:
            expected_mapping = assign_speaker_numbers(ctx.lines)
            # Check speaker tags (S1), (S2), etc.
            for line in ctx.lines:
                spk_id = line.get("speaker_id")
                if spk_id in expected_mapping:
                    expected_num = expected_mapping[spk_id]
                    tag = f"(S{expected_num})"
                    # Verify tag exists in the prompt if line text exists
                    d_text = normalize_text_raw(line.get("text_raw", ""))
                    if d_text and d_text != "." and d_text in all_text:
                        if tag not in all_text:
                            violations.append(
                                self.make_violation(
                                    ctx,
                                    "shots",
                                    f"Dialogue line missing required speaker tag '{tag}'.",
                                )
                            )

        return violations

class PF07_DialoguePunctuation(BaseRule):
    rule_id = "PF-07"
    name = "Dialogue and Visible Text Punctuation"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        for shot in ctx.parsed_prompt.shots:
            for d in shot.dialogue_spans:
                txt = d.text.strip()
                # Must end with ., ?, or ! and NOT ।
                if txt.endswith("।") or txt.endswith("॥"):
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            f"[Shot {shot.number}] dialogue ends with illegal Indic danda '।'; must be normalized to '.', '?', or '!'.",
                        )
                    )
                elif not (txt.endswith(".") or txt.endswith("?") or txt.endswith("!")):
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            f"[Shot {shot.number}] dialogue must end with '.', '?', or '!'.",
                        )
                    )

            # Cross-cut check for N > 1 destination shot
            if shot.number > 1:
                if "<scenetrans>" in shot.text:
                    expected_prefix = "<scenetrans> The audio continues seamlessly across the cut. "
                    if not shot.text.startswith(expected_prefix):
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] cross-cut destination must begin with '{expected_prefix}'.",
                            )
                        )

        return violations

class PF08_SoundFields(BaseRule):
    rule_id = "PF-08"
    name = "Sound Fields Policy"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        policy = ctx.clip.get("audio_policy", "dialogue_only")
        soundscape = ctx.parsed_prompt.get_section_text("overall_soundscape").strip()
        music = ctx.parsed_prompt.get_section_text("non_diegetic_music").strip()

        if policy in {"dialogue_only", "silence"}:
            if soundscape != "N/A":
                violations.append(
                    self.make_violation(
                        ctx,
                        "overall_soundscape",
                        f"Under '{policy}', overall_soundscape must be exactly 'N/A'; found '{soundscape}'.",
                        suggested_text="N/A",
                    )
                )
            if music != "N/A":
                violations.append(
                    self.make_violation(
                        ctx,
                        "non_diegetic_music",
                        f"Under '{policy}', non_diegetic_music must be exactly 'N/A'; found '{music}'.",
                        suggested_text="N/A",
                    )
                )
        elif policy == "custom":
            if soundscape == "N/A":
                violations.append(
                    self.make_violation(
                        ctx,
                        "overall_soundscape",
                        "Under 'custom' audio, overall_soundscape cannot be 'N/A'.",
                    )
                )
            else:
                sc_count = count_sentences(soundscape)
                if not (1 <= sc_count <= 4):
                    violations.append(
                        self.make_violation(
                            ctx,
                            "overall_soundscape",
                            f"Custom soundscape must be 1–4 sentences; counted {sc_count}.",
                        )
                    )

            if music != "N/A":
                mus_count = count_sentences(music)
                if not (1 <= mus_count <= 3):
                    violations.append(
                        self.make_violation(
                            ctx,
                            "non_diegetic_music",
                            f"Custom music must be 1–3 sentences (or N/A); counted {mus_count}.",
                        )
                    )

        return violations

class PF08b_MoodWords(BaseRule):
    rule_id = "PF-08b"
    name = "Music Mood Words and Non-Latin Leaks"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        music = ctx.parsed_prompt.get_section_text("non_diegetic_music")
        mood_data = get_mood_words()

        if music and music != "N/A":
            for err_word in mood_data["errors"]:
                if re.search(rf"\b{err_word}\b", music, re.IGNORECASE):
                    violations.append(
                        self.make_violation(
                            ctx,
                            "non_diegetic_music",
                            f"Illegal mood word '{err_word}' in non_diegetic_music.",
                            severity="error",
                        )
                    )
            for warn_word in mood_data["warnings"]:
                if re.search(rf"\b{warn_word}\b", music, re.IGNORECASE):
                    violations.append(
                        self.make_violation(
                            ctx,
                            "non_diegetic_music",
                            f"Discouraged mood word '{warn_word}' in non_diegetic_music.",
                            severity="warning",
                            blocking=False,
                        )
                    )

        # Check non-Latin text outside <d> spans
        raw_body = ctx.parsed_prompt.raw_body
        outside_d = re.sub(r"<d>.*?</d>", "", raw_body, flags=re.DOTALL)
        outside_d = re.sub(r'"[^"\n]+"', "", outside_d)  # Exclude quoted text
        if NON_LATIN_SCRIPT_RE.search(outside_d):
            violations.append(
                self.make_violation(
                    ctx,
                    "body",
                    "Non-Latin script characters found outside <d> dialogue or quoted signs.",
                )
            )

        return violations

class PF09_CharacterLimitAndFences(BaseRule):
    rule_id = "PF-09"
    name = "Character Limit and Markdown Fences"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        body = ctx.parsed_prompt.raw_body
        code_point_count = len(body)

        if code_point_count > 7000:
            violations.append(
                self.make_violation(
                    ctx,
                    "body",
                    f"Prompt body ({code_point_count} code points) exceeds maximum 7000 Unicode code points.",
                )
            )

        if MARKDOWN_FENCE_RE.search(body):
            violations.append(
                self.make_violation(
                    ctx,
                    "body",
                    "Prompt contains illegal Markdown code fences (``` or ~~~). Plain text only.",
                )
            )

        if MARKDOWN_BULLET_RE.search(body):
            violations.append(
                self.make_violation(
                    ctx,
                    "body",
                    "Prompt contains illegal Markdown bullet lists. Plain text only.",
                )
            )

        return violations

class PF10_EnglishProseCheck(BaseRule):
    rule_id = "PF-10"
    name = "English Prose and Language Detection"
    default_severity = "error"
    basis = "heuristic"
    fixable = True
    overridable = True

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        body = ctx.parsed_prompt.raw_body
        stripped = re.sub(r"<d>.*?</d>", "", body, flags=re.DOTALL)
        stripped = re.sub(r'"[^"\n]+"', "", stripped)

        # Non-Latin characters in stripped prose
        if NON_LATIN_SCRIPT_RE.search(stripped):
            violations.append(
                self.make_violation(
                    ctx,
                    "body",
                    "All prompt fields must be English; non-English detected outside <d> spans.",
                )
            )

        # Indic language tags outside <d>
        indic_tags = ["[Kannada]", "[Hindi]", "[Tamil]", "[Telugu]", "[Malayalam]", "[Marathi]", "[Bengali]"]
        for it in indic_tags:
            if it in stripped:
                violations.append(
                    self.make_violation(
                        ctx,
                        "body",
                        f"Indic language tag '{it}' found outside <d> dialogue span.",
                    )
                )

        return violations

class PF11_RatioConcrete(BaseRule):
    rule_id = "PF-11"
    name = "Aspect Ratio Validity"
    default_severity = "error"
    basis = "structural"
    fixable = False
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        mode = ctx.clip.get("mode")
        ratio = ctx.clip.get("ratio")
        concrete_ratios = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}

        if mode == "T2VA":
            if ratio not in concrete_ratios:
                violations.append(
                    self.make_violation(
                        ctx,
                        "ratio",
                        f"T2VA requires a concrete ratio ({sorted(concrete_ratios)}); cannot be '{ratio}'.",
                    )
                )
        elif mode in {"I2VA", "FL2VA", "L2VA"}:
            if ratio != "adaptive":
                violations.append(
                    self.make_violation(
                        ctx,
                        "ratio",
                        f"{mode} requires 'adaptive' ratio; cannot be '{ratio}'.",
                    )
                )
        elif mode == "REF2VA":
            if ratio != "adaptive" and ratio not in concrete_ratios:
                violations.append(
                    self.make_violation(
                        ctx,
                        "ratio",
                        f"REF2VA ratio must be 'adaptive' or concrete ({sorted(concrete_ratios)}); cannot be '{ratio}'.",
                    )
                )

        return violations

class PF12_ShotPartition(BaseRule):
    rule_id = "PF-12"
    name = "Shot Partition and Word Count"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        shots = ctx.parsed_prompt.shots
        duration_s = ctx.clip.get("duration_s", 15)
        total_duration_ms = duration_s * 1000

        # Check last shot word count
        if shots:
            last_shot = shots[-1]
            if last_shot.word_count < 12:
                violations.append(
                    self.make_violation(
                        ctx,
                        "shots",
                        f"Last shot ([Shot {last_shot.number}]) has fewer than 12 words ({last_shot.word_count}).",
                        severity="warning",
                        blocking=False,
                    )
                )

        # Check timeline gaps/overlaps if shot times are planned in ctx.shots
        if ctx.shots and len(ctx.shots) > 1:
            sorted_shots = sorted(ctx.shots, key=lambda s: s.get("ordinal", 0))
            curr_ms = 0
            for s in sorted_shots:
                s_start = s.get("start_ms", 0)
                s_end = s.get("end_ms", 0)
                if s_start != curr_ms:
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            f"Shot timeline gap or overlap: Shot {s.get('ordinal')} starts at {s_start}ms, expected {curr_ms}ms.",
                        )
                    )
                curr_ms = s_end

            if curr_ms != total_duration_ms:
                violations.append(
                    self.make_violation(
                        ctx,
                        "shots",
                        f"Shot partition ends at {curr_ms}ms, but clip duration is {total_duration_ms}ms.",
                    )
                )

        return violations

class PF13_VideoModelMatrix(BaseRule):
    rule_id = "PF-13"
    name = "Video Model Matrix Limits"
    default_severity = "error"
    basis = "structural"
    fixable = False
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        model = ctx.clip.get("video_model", "MiniMax-H3")
        duration_s = ctx.clip.get("duration_s", 5)
        resolution = ctx.clip.get("resolution", "768P")

        if model == "MiniMax-H3":
            if not (4 <= duration_s <= 15):
                violations.append(
                    self.make_violation(
                        ctx,
                        "video_model",
                        f"MiniMax-H3 allows integer durations 4–15 seconds; given {duration_s}s.",
                    )
                )
            if resolution not in {"768P", "2K"}:
                violations.append(
                    self.make_violation(
                        ctx,
                        "video_model",
                        f"MiniMax-H3 allows resolutions '768P' or '2K'; given '{resolution}'.",
                    )
                )
        elif model == "MiniMax-H3-Max":
            if not (5 <= duration_s <= 15):
                violations.append(
                    self.make_violation(
                        ctx,
                        "video_model",
                        f"MiniMax-H3-Max allows integer durations 5–15 seconds; given {duration_s}s.",
                    )
                )
            if resolution not in {"480P", "768P"}:
                violations.append(
                    self.make_violation(
                        ctx,
                        "video_model",
                        f"MiniMax-H3-Max allows resolutions '480P' or '768P'; given '{resolution}'.",
                    )
                )
        else:
            violations.append(
                self.make_violation(
                    ctx,
                    "video_model",
                    f"Unknown video model '{model}'. Must be MiniMax-H3 or MiniMax-H3-Max.",
                )
            )

        return violations
