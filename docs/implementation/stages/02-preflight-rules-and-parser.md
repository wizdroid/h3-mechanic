# Stage 02: Preflight Rules, Parser & Validation Engine

**Milestone:** M1  
**Specification Reference:** [`specification-0.3.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.3.md) §§1.5, 5.5, 5.6, 9.1–9.6, Appendix A  
**Key Acceptance Criteria:** A-08, A-10, A-11, A-12, A-27, A-34, A-41  

---

## 1. Stage Overview & Scope

Implement the complete deterministic validation engine for H3 Prompt Studio. This includes bundled vocabulary loaders, text and structural parsers, language/syllable estimators, the rule registry, all 35 preflight rules (PF-01 through PF-35), deterministic autofix routines, and the override API.

### Deliverables:
1. `app/resources/`: JSON assets generated from Appendix A (camera verbs, landings, mood words, sound lexicon, voice IDs, style openings, script unicode blocks).
2. `app/validation/parser.py`: Unified prompt parser producing `ParsedPrompt` (mode detector, section isolator, cut-time extractor, camera phrase finder, dialogue span extractor).
3. `app/validation/estimators.py`: Syllable counter for Indic languages, English word counter, speech/shot duration estimator in tenths of a second, speaker number allocator, `text_raw` normalizer.
4. `app/validation/registry.py`: Rule registry with standardized violation schema (§9.4), severity levels (`error`, `warning`), basis (`structural`, `heuristic`), and overridability flags.
5. `app/validation/rules/`: Complete implementations of PF-01 through PF-35.
6. `app/validation/autofix.py`: Deterministic 5-step autofix engine (§9.6).
7. `app/api/validation_routes.py`: Endpoints for `validate-inputs` (Stage 0), `preflight`, and `override`.
8. `tests/test_stage_02.py`: Comprehensive test suite with passing and failing fixtures for all rules.

---

## 2. Step-by-Step Implementation Instructions

### Step 2.1: Derived Vocabularies (`app/resources/`)
Populate static JSON resources strictly matching Appendix A:
- `camera_moves.json`: Exact verbs and modifiers (Static, Push, Pull, Zoom, Pan, Tilt, Truck, Pedestal, Arc, Track, POV, Shake, Roll).
- `landings.json`: `[" toward ", " revealing ", " onto ", " as "]`.
- `mood_words.json`: Errors (`["tense", "sad"]`), Warnings (21 words from §A.11).
- `sound_lexicon.json`: 27 banned sound words under dialogue-only / silence (§9.6).
- `script_ranges.json`: Indic Unicode ranges and virama code points (§9.6).
- `styles.json`: Exact style prefixes and descriptions (§A.10).

### Step 2.2: Deterministic Estimators (`app/validation/estimators.py`)
Implement the estimators per §9.5:
- `normalize_text_raw(text: str) -> str`: Strip trailing whitespace; convert `।` or `॥` to `.`; ensure ends in `.`, `?`, or `!`.
- `count_indic_syllables(text: str, language: str) -> int`: Code point traversal in the script block, counting `Lo` category characters not immediately preceded by a virama.
- `count_english_words(text: str) -> int`: Match regex `[A-Za-z0-9]+(?:'[A-Za-z]+)?`.
- `estimate_line_duration_tenths(text_raw: str, language: str) -> int`:
  - English: `words * 4` (tenths).
  - Indic: `(syllables * 20 + 8) // 9` (tenths).
  - Total line tenths: `speech_tenths + 5` (adds 0.5s pause).
- `assign_speaker_numbers(lines: list) -> dict`: Order lines by `(shot.start_ms, line_order, id)`, assign sequential integers starting at 1 upon first appearance.

### Step 2.3: Prompt Parser (`app/validation/parser.py`)
Parse raw prompt text into a strongly typed `ParsedPrompt` object:
- Mode detection: instruction line regex, `subject_definitions:` header, or `integrated_multimodal_description:`.
- Section extraction: headers `subject_definitions:`, `summary:`, `retention_analysis:`, `detailed_description:`, `overall_soundscape:`, `non_diegetic_music:`.
- Shot parser: `\[Shot (\d+)\]` with timestamp regex `CUT_TIME_RE = r"\[Shot (\d+)\] At (\d{2}):(\d{2})\.(\d{3}), the camera cuts to "`.
- Camera phrase search: scan from longest to shortest against official table (§9.6).
- Dialogue span parser: `<d>\[([A-Za-z]+)\] (.*?)</d>`.

### Step 2.4: Preflight Rule Implementations (`app/validation/rules/`)
Implement all PF rules defined in §9.1 and §9.2:
- **PF-01:** Structural layout check (multiline REF2VA vs single-line T2VA/frames).
- **PF-02:** Cut timestamp format `MM:SS.mmm`, strictly increasing, below duration.
- **PF-03:** Shot count within Appendix A.4 limits; FL2VA 1-shot waiver.
- **PF-04:** Official camera move with landing. Ban all speed/amplitude modifiers on Static, POV, and Shake (S-08).
- **PF-05:** Face heuristic: CU/MCU/MS for speaking/readable faces; 85mm/50mm framing; mouth closure check.
- **PF-06:** Speech sentence format equality with §8.0 expansion.
- **PF-07:** Verbatim dialogue inside `<d>`. Cross-cut prefix placement immediately after cut header for $N > 1$ (S-04).
- **PF-08 / PF-08b:** Sound fields `N/A` under dialogue-only/silence; mood words checks.
- **PF-09:** Character count $\le 7000$ Unicode code points (excluding final export newline).
- **PF-10:** English-only check outside `<d>` and visible quotes.
- **PF-11:** Concrete ratio for T2VA; `adaptive` for frame modes.
- **PF-20:** Reference token budgets ($\le 9$ pictures, $\le 3$ videos, $\le 3$ audio, $\le 12$ files). Image dimensions are optional metadata; ratio/dimension checks are advisory warnings (S-02).
- **PF-23:** Subject definitions match deterministic formulas for 0, 1, or multiple linked pictures (S-03).
- **PF-28:** Template integrity: every `{{Lk}}` and `{{Tm}}` appears once without loss (S-05).
- **PF-31:** Stage 0 native script verification; reject pure Romanized input.
- **PF-34:** Sound lexicon check on shot prose under dialogue-only/silence.
- **PF-35:** House audio sentence presence and position.

### Step 2.5: Deterministic Autofix Engine (`app/validation/autofix.py`)
Implement the 5 sequential autofix passes (§9.6):
1. Fix timestamp colon to dot (`00:03:000` → `00:03.000`).
2. Fix `the shot cuts to` → `the camera cuts to`.
3. Normalize camera move casing (`the camera pushes in` → `The camera pushes in`).
4. Replace colon before `<d>` with comma.
5. Sound field normalization to `N/A` under `dialogue_only`/`silence` across both inline and multiline REF2VA sections (S-06), inserting/removing the house audio sentence.

### Step 2.6: Validation API Routes (`app/api/validation_routes.py`)
- `POST /api/clips/{id}/validate-inputs`: Runs Stage 0 validation (budgets, ratios, model matrix, native scripts) before any LLM execution.
- `POST /api/clips/{id}/preflight`: Parses prompt and runs full PF suite, persisting `preflight_json`.
- `POST /api/clips/{id}/override`: Records user override on heuristic rules (PF-04, PF-05, PF-10, PF-34) with mandatory audit note (§9.4).

---

## 3. Calibrated Master Prompt for Stage 02

```text
You are an expert systems engineer implementing Stage 02 (Validation Engine and Rules) of H3 Prompt Studio strictly according to docs/specifications/specification-0.3.md.

Task:
Implement the validation engine, prompt parser, estimators, vocabulary loaders, preflight rules PF-01 through PF-35, deterministic autofix, and validation endpoints.

Strict Boundaries:
1. Follow the canonical validation contract (§1.5):
   - All validation rules reside in app/validation/rules/ registered through app/validation/registry.py.
   - Return normalized violation objects matching Section 9.4:
     { rule_id, section, severity, basis, message, suggested_text, blocking, fixable, overridable, overridden }
2. Estimators (§9.5):
   - Syllable counter counts Lo code points in target script blocks not preceded by virama.
   - Line length calculation in tenths of a second.
   - Speaker number assignment strictly deterministic based on (start_ms, line_order, id).
3. Preflight Rules Specifications:
   - S-02 / PF-20: Image width/height are optional metadata; dimensions outside 256–5760 px or ratio [0.4, 2.5] emit advisory warnings (severity: "warning", blocking: false). Budgets (≤ 9 images, ≤ 3 videos, ≤ 3 audio, ≤ 12 files; 2–15s duration) remain hard blocking errors.
   - S-03 / PF-23: Subject definition formulas must support 0 pictures (text-only), 1 picture (identity anchor), and multiple pictures (face + outfit).
   - S-04 / PF-07: For N > 1, destination cross-cut prefix follows the cut header:
     "[Shot N] At MM:SS.mmm, the camera cuts to <scenetrans> The audio continues seamlessly across the cut. "
   - S-08 / PF-04: Static, POV, and Shake camera moves forbid all speed and amplitude modifiers.
4. Deterministic Autofix (§9.6):
   - S-06: Rule 5 must normalize both single-line (T2VA/frames) and multiline REF2VA sound fields to N/A under dialogue_only/silence.
5. Overrides (§9.4):
   - Only heuristic rules (PF-04, PF-05, PF-10, PF-34) may be overridden via POST /api/clips/{id}/override with a mandatory note. Structural rules can NEVER be overridden.
6. Tests:
   - Create tests/test_stage_02.py containing passing and failing test fixtures for all 35 rules, estimators, autofix passes, and override mechanics.

Do not write UI components in this stage. Focus on robust, production-grade parser and validation code.
```

---

## 4. Integrated Verification Checkpoints

Run the automated verification suite:
```bash
pytest tests/test_stage_02.py -v
```

### Checkpoint Verifications:
1. **PF-04 Camera Modifiers:**
   - Prompt with `The camera holds a static shot at slow speed` → Assert blocking error (PF-04).
   - Prompt with `The camera pushes in slowly toward the door` → Assert passes.
2. **PF-20 Optional Dimensions:**
   - REF2VA clip with image references lacking `width_px`/`height_px` → Assert passes Stage 0 validation.
   - REF2VA clip with 10 image references → Assert blocking error (PF-20).
3. **PF-07 Cross-Cut Destination:**
   - Destination shot $N=2$ with `<scenetrans> [Shot 2] At 00:03.000...` → Assert error.
   - Destination shot $N=2$ with `[Shot 2] At 00:03.000, the camera cuts to <scenetrans> The audio continues seamlessly across the cut. ` → Assert passes.
4. **Override Mechanism:**
   - Apply override to PF-05 (face heuristic) with note → Assert `overridden == True` and clip unblocked.
   - Attempt override on PF-01 (structural) → Assert HTTP 422 rejected.
