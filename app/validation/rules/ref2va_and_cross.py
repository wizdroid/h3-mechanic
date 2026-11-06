"""Preflight rules PF-20 through PF-35 for REF2VA and cross-mode validation (§9.2)."""

from __future__ import annotations
import re
from typing import Any, Optional
from app.validation.registry import BaseRule, ValidationContext, Violation
from app.resources.vocab import (
    get_task_types,
    get_retention_markers,
    get_sound_lexicon,
    get_scripts,
    HOUSE_SENTENCE,
)
from app.validation.estimators import estimate_speech_tenths

TAG_STACK_RE = re.compile(r"\b(4k|masterpiece|high quality|epic|dynamic camera|cool vfx)\b", re.IGNORECASE)
EMOTION_WORDS = [
    "nervous", "angry", "sad", "happy", "scared", "afraid",
    "emotional", "upset", "excited", "anxious"
]
PHYSICAL_TOKENS = [
    "eye", "eyes", "brow", "brows", "lip", "lips", "mouth", "jaw",
    "breath", "hand", "hands", "shoulder", "shoulders", "gaze", "tear", "smile"
]

class PF20_ReferenceLimits(BaseRule):
    rule_id = "PF-20"
    name = "Reference Limits and Budgets"
    default_severity = "error"
    basis = "structural"
    fixable = False
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        mode = ctx.clip.get("mode")
        refs = ctx.references
        images = [r for r in refs if r.get("kind") == "image"]
        videos = [r for r in refs if r.get("kind") == "video"]
        audio = [r for r in refs if r.get("kind") == "audio"]

        if mode == "T2VA":
            if len(refs) > 0:
                violations.append(
                    self.make_violation(
                        ctx, "references", f"T2VA mode does not permit reference tokens; found {len(refs)}."
                    )
                )
            return violations

        if mode in {"I2VA", "L2VA"}:
            if len(images) != 1:
                violations.append(
                    self.make_violation(
                        ctx, "references", f"{mode} requires exactly 1 image reference; found {len(images)}."
                    )
                )
            if len(videos) > 0 or len(audio) > 0:
                violations.append(
                    self.make_violation(
                        ctx, "references", f"{mode} does not permit audio or video references."
                    )
                )
            for img in images:
                self._check_image_dims(ctx, img, violations)
            if not ctx.clip.get("manual_draft") and not (ctx.clip.get("action_text") or "").strip():
                violations.append(
                    self.make_violation(ctx, "action_text", f"{mode} requires a non-empty action text.")
                )
            return violations

        if mode == "FL2VA":
            if len(images) != 2:
                violations.append(
                    self.make_violation(
                        ctx, "references", f"FL2VA requires exactly 2 image references (first frame and last frame); found {len(images)}."
                    )
                )
            if len(videos) > 0 or len(audio) > 0:
                violations.append(
                    self.make_violation(
                        ctx, "references", "FL2VA does not permit audio or video references."
                    )
                )
            for img in images:
                self._check_image_dims(ctx, img, violations)
            if not ctx.clip.get("manual_draft") and not (ctx.clip.get("action_text") or "").strip():
                violations.append(
                    self.make_violation(ctx, "action_text", "FL2VA requires a non-empty transition input.")
                )
            return violations

        if mode != "REF2VA":
            return violations

        if len(images) > 9:
            violations.append(
                self.make_violation(
                    ctx, "references", f"Images budget exceeded ({len(images)} > 9)."
                )
            )
        if len(videos) > 3:
            violations.append(
                self.make_violation(
                    ctx, "references", f"Videos budget exceeded ({len(videos)} > 3)."
                )
            )
        if len(audio) > 3:
            violations.append(
                self.make_violation(
                    ctx, "references", f"Audio budget exceeded ({len(audio)} > 3)."
                )
            )
        if len(refs) > 12:
            violations.append(
                self.make_violation(
                    ctx, "references", f"Total files budget exceeded ({len(refs)} > 12)."
                )
            )

        video_dur_total = 0
        for v in videos:
            dur = v.get("duration_ms")
            if dur is None or not (2000 <= dur <= 15000):
                violations.append(
                    self.make_violation(
                        ctx, "references", f"Video reference {v.get('ordinal')} duration ({dur}ms) must be 2000–15000ms."
                    )
                )
            else:
                video_dur_total += dur

        if video_dur_total > 15000:
            violations.append(
                self.make_violation(
                    ctx, "references", f"Total video references duration ({video_dur_total}ms) exceeds 15000ms."
                )
            )

        audio_dur_total = 0
        for a in audio:
            dur = a.get("duration_ms")
            if dur is None or not (2000 <= dur <= 15000):
                violations.append(
                    self.make_violation(
                        ctx, "references", f"Audio reference {a.get('ordinal')} duration ({dur}ms) must be 2000–15000ms."
                    )
                )
            else:
                audio_dur_total += dur

        if audio_dur_total > 15000:
            violations.append(
                self.make_violation(
                    ctx, "references", f"Total audio references duration ({audio_dur_total}ms) exceeds 15000ms."
                )
            )

        # Image dimensions check (advisory S-02: warning, non-blocking)
        for img in images:
            self._check_image_dims(ctx, img, violations)

        return violations

    def _check_image_dims(self, ctx: ValidationContext, img: dict[str, Any], violations: list[Violation]) -> None:
        w = img.get("width_px")
        h = img.get("height_px")
        if w is not None and h is not None:
            dim_out_of_range = not (256 <= w <= 5760 and 256 <= h <= 5760)
            ratio = w / h if h != 0 else 0
            ratio_out_of_range = not (0.4 <= ratio <= 2.5)
            if dim_out_of_range or ratio_out_of_range:
                violations.append(
                    self.make_violation(
                        ctx,
                        "references",
                        f"Image <Picture {img.get('ordinal', 1)}> dimensions ({w}x{h}, ratio {ratio:.2f}) are outside recommended bounds (256–5760 px, ratio [0.4, 2.5]).",
                        severity="warning",
                        blocking=False,
                    )
                )

class PF21_SummaryTaskTypes(BaseRule):
    rule_id = "PF-21"
    name = "Summary Task Types"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        if ctx.clip.get("mode") != "REF2VA":
            return violations

        summary = ctx.parsed_prompt.get_section_text("summary").strip()
        m = re.match(r"^\[(.*?)\]", summary)
        if not m:
            violations.append(
                self.make_violation(
                    ctx,
                    "summary",
                    "Summary must open with one bracketed task type from Appendix A.9.",
                )
            )
            return violations

        task_types_raw = m.group(1).split(" + ")
        valid_types = set(get_task_types())
        seen_types = set()

        for t in task_types_raw:
            t_clean = t.strip()
            if t_clean not in valid_types:
                violations.append(
                    self.make_violation(
                        ctx,
                        "summary",
                        f"Summary task type '{t_clean}' is not an approved task type from Appendix A.9.",
                    )
                )
            if t_clean in seen_types:
                violations.append(
                    self.make_violation(
                        ctx,
                        "summary",
                        f"Summary has repeated task type '{t_clean}'.",
                    )
                )
            seen_types.add(t_clean)

        return violations

class PF22_RetentionMarkers(BaseRule):
    rule_id = "PF-22"
    name = "Retention Analysis Markers"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        if ctx.clip.get("mode") != "REF2VA":
            return violations

        ret_sec = ctx.parsed_prompt.sections.get("retention_analysis")
        if not ret_sec:
            return violations

        valid_markers_data = get_retention_markers()
        valid_markers = set(valid_markers_data["visual"] + valid_markers_data["audio"])

        for line in ret_sec.lines:
            if re.search(r"\(S\d+\)|\(Sx\)", line, re.IGNORECASE):
                violations.append(
                    self.make_violation(
                        ctx,
                        "retention_analysis",
                        "Retention analysis must not contain speaker tags such as '(Sx)'.",
                    )
                )

            m = re.search(r":\s*([a-z_]+)\s*-\s*", line)
            if m:
                marker = m.group(1).strip()
                if marker not in valid_markers:
                    violations.append(
                        self.make_violation(
                            ctx,
                            "retention_analysis",
                            f"Invalid retention marker '{marker}'. Allowed: {sorted(valid_markers)}.",
                        )
                    )
            else:
                violations.append(
                    self.make_violation(
                        ctx,
                        "retention_analysis",
                        f"Retention line does not match format '<Label>...: <marker> - <reason>': {line}",
                    )
                )

        return violations

class PF23_SubjectDefinitionsFormulas(BaseRule):
    rule_id = "PF-23"
    name = "Subject Definitions Formulas and References"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        if ctx.clip.get("mode") != "REF2VA":
            return violations

        sec = ctx.parsed_prompt.sections.get("subject_definitions")
        if not sec:
            return violations

        lines = sec.lines
        subj_lines = [l for l in lines if l.startswith("<Subject ")]
        pic_anchor_lines = [l for l in lines if l.startswith("<Picture ")]
        audio_lines = [l for l in lines if l.startswith("<Audio ")]

        # Check that subjects exist in table
        for sl in subj_lines:
            m = re.match(r"^<Subject (\d+)> is the (.*)$", sl)
            if not m:
                violations.append(
                    self.make_violation(
                        ctx,
                        "subject_definitions",
                        f"Subject definition line does not match formula: '{sl}'.",
                    )
                )

        # Check reference tokens appear in definitions
        refs = ctx.references
        for r in refs:
            k = r.get("kind", "")
            token = f"<Picture {r.get('ordinal')}>" if k == "image" else f"<{k.capitalize()} {r.get('ordinal')}>"
            if token not in sec.content:
                violations.append(
                    self.make_violation(
                        ctx,
                        "subject_definitions",
                        f"Reference row {token} does not appear in subject_definitions.",
                    )
                )

        return violations

class PF24_StyleSentenceBeforeShot1(BaseRule):
    rule_id = "PF-24"
    name = "REF2VA Style Opening"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        if ctx.clip.get("mode") != "REF2VA":
            return violations

        p = ctx.parsed_prompt
        if not p.style_line or not p.style_line.startswith("The target video is "):
            violations.append(
                self.make_violation(
                    ctx,
                    "detailed_description",
                    "REF2VA detailed_description must begin with a style sentence starting 'The target video is …' before [Shot 1].",
                )
            )

        return violations

class PF25_SpeakingSubjectsNotation(BaseRule):
    rule_id = "PF-25"
    name = "Speaking Subjects and Audio References"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        if ctx.clip.get("mode") != "REF2VA":
            return violations

        # Speaking subjects written <Subject N> (Sx)
        # Check audio lines: <Audio N> is the voice-timbre reference for <Subject N> (Sx).
        # And timbre-only refs carry no original words.
        sec = ctx.parsed_prompt.sections.get("subject_definitions")
        if sec:
            for l in sec.lines:
                if l.startswith("<Audio "):
                    if not re.search(r"<Audio \d+> is the voice-timbre reference for .*", l):
                        violations.append(
                            self.make_violation(
                                ctx,
                                "subject_definitions",
                                f"Audio reference line does not match formula: '{l}'.",
                            )
                        )

        return violations

class PF26_DetailedDescriptionWordCount(BaseRule):
    rule_id = "PF-26"
    name = "Detailed Description Word Count"
    default_severity = "warning"
    basis = "structural"
    fixable = False
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        if ctx.clip.get("mode") != "REF2VA":
            return violations

        det_sec = ctx.parsed_prompt.sections.get("detailed_description")
        if not det_sec:
            return violations

        words = len(det_sec.content.split())
        dialogue_lines_count = len(ctx.lines)
        duration_s = ctx.clip.get("duration_s", 15)

        total_speech_tenths = sum(
            estimate_speech_tenths(l.get("text_raw", "") or l.get("text", ""), l.get("language", "English"))
            for l in ctx.lines
        )

        is_exempt = (dialogue_lines_count >= 3) or (total_speech_tenths / 10 > 0.4 * duration_s)

        if not is_exempt and not (350 <= words <= 500):
            violations.append(
                self.make_violation(
                    ctx,
                    "detailed_description",
                    f"detailed_description word count ({words}) outside recommended 350–500 words.",
                    severity="warning",
                    blocking=False,
                )
            )

        return violations

class PF27_TokenContamination(BaseRule):
    rule_id = "PF-27"
    name = "Mode Token Contamination"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        mode = ctx.clip.get("mode")
        raw = ctx.parsed_prompt.raw_body

        if mode == "T2VA":
            for token in ["<Picture", "<Subject", "<Audio", "<Video"]:
                if token in raw:
                    violations.append(
                        self.make_violation(
                            ctx,
                            "body",
                            f"T2VA prompt must not contain REF2VA token '{token}'.",
                        )
                    )
        elif mode in {"I2VA", "FL2VA", "L2VA"}:
            for token in ["<Subject", "<Audio", "<Video"]:
                if token in raw:
                    violations.append(
                        self.make_violation(
                            ctx,
                            "body",
                            f"{mode} prompt must not contain REF2VA token '{token}'.",
                        )
                    )
            for header in ["subject_definitions:", "retention_analysis:", "detailed_description:"]:
                if header in raw:
                    violations.append(
                        self.make_violation(
                            ctx,
                            "body",
                            f"{mode} prompt must not contain REF2VA section header '{header}'.",
                        )
                    )
        elif mode == "REF2VA":
            # Must not contain frame instruction lines
            if "How the reference pictures align with the target video" in raw:
                violations.append(
                    self.make_violation(
                        ctx,
                        "body",
                        "REF2VA prompt must not contain frame-mode instruction lines.",
                    )
                )

        return violations

class PF28_TemplateIntegrity(BaseRule):
    rule_id = "PF-28"
    name = "Template Integrity and Placeholder Remainder"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        raw = ctx.parsed_prompt.raw_body

        if "{{" in raw or "}}" in raw:
            violations.append(
                self.make_violation(
                    ctx,
                    "body",
                    "Prompt body contains unexpanded template placeholders ('{{' or '}}').",
                )
            )
        if "{{V:" in raw:
            violations.append(
                self.make_violation(
                    ctx,
                    "body",
                    "Prompt body contains illegal placeholder '{{V:'.",
                )
            )

        return violations

class PF29_PlanProseAgreement(BaseRule):
    rule_id = "PF-29"
    name = "Plan–Prose Agreement"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        mode = ctx.clip.get("mode")
        if mode not in {"T2VA", "I2VA", "FL2VA", "L2VA"}:
            return violations

        if ctx.shots:
            shots_by_ord = {s.get("ordinal"): s for s in ctx.shots}
            for parsed_shot in ctx.parsed_prompt.shots:
                planned = shots_by_ord.get(parsed_shot.number)
                if planned:
                    # Check camera verb if specified in plan
                    planned_verb = planned.get("camera_move") or planned.get("camera_phrase")
                    if planned_verb and parsed_shot.camera_hits:
                        if planned_verb.lower() not in parsed_shot.camera_hits[0].lower():
                            violations.append(
                                self.make_violation(
                                    ctx,
                                    "shots",
                                    f"[Shot {parsed_shot.number}] written camera move does not match planned move '{planned_verb}'.",
                                )
                            )

        return violations

class PF30_StalePrompt(BaseRule):
    rule_id = "PF-30"
    name = "Stale Prompt Check"
    default_severity = "error"
    basis = "structural"
    fixable = False
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        clip_rev = ctx.clip.get("inputs_revision", 1)
        prompt_rev = ctx.prompt.get("inputs_revision") if ctx.prompt else clip_rev

        if prompt_rev is not None and prompt_rev != clip_rev:
            violations.append(
                self.make_violation(
                    ctx,
                    "prompt",
                    f"Inputs changed since this draft (prompt revision {prompt_rev} ≠ clip revision {clip_rev}). Must regenerate.",
                )
            )

        return violations

class PF31_NativeScriptInput(BaseRule):
    rule_id = "PF-31"
    name = "Native Script Input Verification"
    default_severity = "error"
    basis = "structural"
    fixable = False
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        scripts = get_scripts()

        for line in ctx.lines:
            lang = line.get("language", "English")
            text = line.get("text_raw", "")
            if lang != "English" and text:
                lang_info = scripts.get(lang)
                if lang_info:
                    start = lang_info["range_start"]
                    end = lang_info["range_end"]
                    has_native = any(start <= ord(c) <= end for c in text)
                    if not has_native:
                        violations.append(
                            self.make_violation(
                                ctx,
                                "inputs",
                                f"Dialogue line for language '{lang}' must contain native script ({lang_info['script']}); purely romanized text is rejected.",
                            )
                        )

        return violations

class PF32_OnScreenTextLength(BaseRule):
    rule_id = "PF-32"
    name = "On-Screen Text Word Count and Subtitles"
    default_severity = "warning"
    basis = "structural"
    fixable = False
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        body = ctx.parsed_prompt.raw_body

        if re.search(r"\bsubtitles?\b", body, re.IGNORECASE):
            violations.append(
                self.make_violation(
                    ctx,
                    "body",
                    "Prompt contains request for subtitles; add subtitles during video editing instead.",
                    severity="warning",
                    blocking=False,
                )
            )

        for shot in ctx.parsed_prompt.shots:
            for ost in shot.onscreen_texts:
                words = ost.split()
                if len(words) > 3:
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            f"[Shot {shot.number}] on-screen text \"{ost}\" exceeds 3 words ({len(words)} words).",
                            severity="warning",
                            blocking=False,
                        )
                    )

        return violations

class PF33_FillerAndTagStack(BaseRule):
    rule_id = "PF-33"
    name = "Filler Words and Abstract Emotions"
    default_severity = "warning"
    basis = "heuristic"
    fixable = False
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        body = ctx.parsed_prompt.raw_body

        # Check tag-stack words (always warn)
        for m in TAG_STACK_RE.finditer(body):
            violations.append(
                self.make_violation(
                    ctx,
                    "body",
                    f"Prompt contains generic quality filler tag '{m.group(0)}'.",
                    severity="warning",
                    blocking=False,
                )
            )

        # Check emotion words per shot
        for shot in ctx.parsed_prompt.shots:
            shot_text = shot.text
            has_physical = any(re.search(rf"\b{tok}\b", shot_text, re.IGNORECASE) for tok in PHYSICAL_TOKENS)
            if not has_physical:
                for ew in EMOTION_WORDS:
                    if re.search(rf"\b{ew}\b", shot_text, re.IGNORECASE):
                        violations.append(
                            self.make_violation(
                                ctx,
                                "shots",
                                f"[Shot {shot.number}] contains abstract emotion '{ew}' without observable physical cues.",
                                severity="warning",
                                blocking=False,
                            )
                        )

        return violations

class PF34_SoundLexicon(BaseRule):
    rule_id = "PF-34"
    name = "Sound Lexicon under Dialogue Only or Silence"
    default_severity = "error"
    basis = "heuristic"
    fixable = True
    overridable = True

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        policy = ctx.clip.get("audio_policy", "dialogue_only")
        if policy == "custom":
            return violations

        lexicon = get_sound_lexicon()

        for shot in ctx.parsed_prompt.shots:
            txt = shot.text
            # Remove house sentence if present
            txt = txt.replace(HOUSE_SENTENCE, "")
            # Remove <d>...</d>
            txt = re.sub(r"<d>.*?</d>", "", txt, flags=re.DOTALL)
            # Remove straight double quotes
            txt = re.sub(r'"[^"\n]+"', "", txt)

            for sound_word in lexicon:
                if re.search(rf"\b{sound_word}\b", txt, re.IGNORECASE):
                    violations.append(
                        self.make_violation(
                            ctx,
                            "shots",
                            f"[Shot {shot.number}] contains banned sound word '{sound_word}' under '{policy}' audio policy.",
                        )
                    )

        return violations

class PF35_HouseAudioSentence(BaseRule):
    rule_id = "PF-35"
    name = "House Sentence Audio Directive"
    default_severity = "error"
    basis = "structural"
    fixable = True
    overridable = False

    def validate(self, ctx: ValidationContext) -> list[Violation]:
        violations: list[Violation] = []
        policy = ctx.clip.get("audio_policy", "dialogue_only")
        mode = ctx.clip.get("mode")
        body = ctx.parsed_prompt.raw_body

        occurrences = body.count(HOUSE_SENTENCE)

        if policy == "dialogue_only":
            if occurrences != 1:
                violations.append(
                    self.make_violation(
                        ctx,
                        "audio",
                        f"Under 'dialogue_only', the house sentence must occur exactly once; found {occurrences}.",
                        suggested_text=HOUSE_SENTENCE,
                    )
                )
            else:
                # Check position (§7.6):
                # In REF2VA: last sentence of style line before [Shot 1].
                # In other modes: immediately after the first sentence of [Shot 1].
                if mode == "REF2VA":
                    if ctx.parsed_prompt.style_line and not ctx.parsed_prompt.style_line.strip().endswith(HOUSE_SENTENCE):
                        violations.append(
                            self.make_violation(
                                ctx,
                                "detailed_description",
                                "In REF2VA, house sentence must be the last sentence of the style line, before [Shot 1].",
                            )
                        )
                else:
                    if ctx.parsed_prompt.shots:
                        shot1 = ctx.parsed_prompt.shots[0]
                        # Check shot 1 has house sentence
                        if HOUSE_SENTENCE not in shot1.text:
                            violations.append(
                                self.make_violation(
                                    ctx,
                                    "shots",
                                    "In T2VA/frame modes, house sentence must appear in [Shot 1].",
                                )
                            )
        else:
            # Under custom or silence, occurrences must be 0
            if occurrences != 0:
                violations.append(
                    self.make_violation(
                        ctx,
                        "audio",
                        f"Under '{policy}', the house sentence must not be present; found {occurrences}.",
                    )
                )

        return violations
