# Stage 05: Generator Web Shell & T2VA Mode End-to-End

**Milestone:** M4  
**Specification Reference:** [`specification-0.3.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.3.md) §§4.1–4.4.2, 7.1, 7.2, 7.6, 8.1, 8.1b  
**Key Acceptance Criteria:** A-01, A-22, A-23, A-29  

---

## 1. Stage Overview & Scope

Build the client-side Web UI shell with Nord styling, implement the two-level tab navigation, wire up the shared clip metadata bar, and deliver the complete end-to-end implementation for **T2VA (Text-to-Video-Audio)** mode.

### Deliverables:
1. `app/web/index.html`: Single-page web application skeleton with top-level tabs (Generator, Settings) and mode sub-tabs (T2VA, I2VA, FL2VA, L2VA, REF2VA).
2. `app/web/css/nord.css`: Vanilla CSS featuring authentic Nord theme palettes (Nord Dark default, Nord Coloured, Nord Light) with monospace prompt preview containers.
3. `app/web/js/app.js`: Core ES module application controller managing clip state, streaming API consumption via `fetch` + `ReadableStream`, preflight badge rendering, and theme toggling.
4. `app/web/js/modes/t2va.js`: T2VA mode view component (seed text input, dialogue lines editor, manual draft toggle, action triggers).
5. `app/api/t2va_routes.py`: T2VA pipeline endpoint orchestrating `seed_elaboration` → `prose_writer` → deterministic render → preflight.
6. `tests/test_stage_05.py`: Automated tests verifying T2VA pipeline execution, fallback prose stitching, Stage 0 input blocking with 0 Ollama calls, and static asset delivery.

---

## 2. Step-by-Step Implementation Instructions

### Step 5.1: Nord CSS Theme & Web Shell (`app/web/`)
- Color Palette Variables:
  - Polar Night: `nord0` (`#2e3440`) to `nord3` (`#4c566a`).
  - Snow Storm: `nord4` (`#d8dee9`) to `nord6` (`#eceff4`).
  - Frost: `nord7` (`#8fbcbb`) to `nord10` (`#5e81ac`).
  - Aurora: `nord11` (`#bf616a`, errors), `nord13` (`#ebcb8b`, warnings), `nord14` (`#a3be8c`, success).
- Top-level Tab Router:
  - Top bar: Generator | Settings.
  - Sub-navigation under Generator: T2VA | I2VA | FL2VA (flf2va) | L2VA (lf2va) | REF2VA.
- Shared Clip Metadata Bar:
  - Project dropdown, clip selector, clip rename input.
  - Duration slider (model-constrained: 4–15s for H3, 5–15s for H3-Max).
  - Resolution selector (`768P`/`2K` for H3, `480P`/`768P` for H3-Max).
  - Ratio selector (concrete values for T2VA; locked adaptive for frames).
  - Style selector (`plain` with 6 allowed pairs; 4 named styles).
  - Audio policy (`dialogue_only`, `custom`, `silence`).

### Step 5.2: T2VA Mode Form & Dialogue Builder (`app/web/js/modes/t2va.js`)
- Inputs:
  - `seed_text` textarea (required).
  - Dialogue lines table: speaker persona, language dropdown (8 supported Indic/English languages), native-script input textarea, optional English gloss, delivery dropdown, voiceover/cutoff toggles.
  - Manual draft checkbox and manual template textarea.
- Action Controls:
  - `[Generate Prompt ▸]` button.
  - `[Run Preflight]` button.
  - `[Export Clip]` button.
  - Cancel button (visible during active generation).

### Step 5.3: T2VA Backend Pipeline (`app/api/t2va_routes.py`)
Wire up the pipeline stages:
1. **Stage 0 Input Check:** Validate concrete ratio, valid duration/resolution, native script in dialogue lines. If invalid, return HTTP 422 with 0 Ollama calls (Criterion A-29).
2. **`seed_elaboration`:** Produce JSON plan matching the schema (§8.1) with characters, setting, beats, shots, voices.
3. **`prose_writer`:** Produce `body_template` from plan (§8.1b).
   - If `prose_writer` fails twice and plan is valid: engage `fallback_prose` stitcher and set `prompts.prose_fallback = 1`.
4. **Renderer:** Expand speech placeholders `{{Lk}}` and on-screen text `{{Tm}}`, insert dialogue-only house audio sentence, append overall soundscape and non-diegetic music.
5. **Preflight Validator:** Run full validation suite on rendered prompt. If fixable errors exist and auto-fix enabled, execute repair loop.

### Step 5.4: Live Preflight Panel UI
Display validation checklist results live in the UI:
- Green: Passing rules.
- Red: Blocking errors (highlighting whether fixable by LLM or requiring input changes).
- Yellow: Advisory warnings (e.g. shot word count, non-blocking dimension notes).
- Blue / Shield: Overridden heuristic rules with user note.

---

## 3. Calibrated Master Prompt for Stage 05

```text
You are an expert full-stack engineer implementing Stage 05 (Generator Web Shell & T2VA Mode) of H3 Prompt Studio strictly according to docs/specifications/specification-0.3.md.

Task:
Build the web UI shell, Nord styling, shared clip metadata bar, and the complete end-to-end T2VA generation pipeline.

Strict Boundaries:
1. Web UI & Styling (§4.1–§4.3, Criterion A-22, A-23):
   - Vanilla JS ES modules (no npm, no Webpack/Vite build step).
   - Nord theme CSS with nord-dark (default), nord-coloured, and nord-light switchable via body class.
   - Two top-level tabs (Generator, Settings) and 5 mode sub-tabs populated from /api/modes.
   - Monospace font for prompt previews with syntax coloring for section tags.
2. Shared Clip Bar (§4.4.1):
   - Duration slider strictly constrained by video model: MiniMax-H3 (4–15s), MiniMax-H3-Max (5–15s).
   - T2VA ratio must be concrete select (21:9, 16:9, 4:3, 1:1, 3:4, 9:16), never adaptive.
3. T2VA Pipeline Execution (§7.2, §8.1, §8.1b, Criterion A-01):
   - Run Stage 0 validation: pure Romanized Indic dialogue lines or adaptive ratio must reject immediately with ZERO Ollama calls (Criterion A-29).
   - seed_elaboration (JSON schema) -> prose_writer -> deterministic renderer -> preflight.
   - If prose_writer fails twice, fallback_prose stitches shots and sets prose_fallback = 1 while guaranteeing that all {{Lk}} placeholders are preserved (S-05).
   - Output format: exactly 3 fields (integrated_multimodal_description, overall_soundscape, non_diegetic_music) on single lines, blank line between fields, dialogue-only house sentence placed immediately after first sentence of [Shot 1].
4. Tests:
   - Create tests/test_stage_05.py verifying:
     * Static assets (index.html, nord.css, js modules) load cleanly.
     * T2VA generation end-to-end with mock Ollama producing valid 3-field output.
     * Fallback prose triggered when prose writer fails twice.
     * Stage 0 rejection makes 0 Ollama requests.

Do not implement frame modes (I2VA/FL2VA/L2VA) or REF2VA specifics in this stage.
```

---

## 4. Integrated Verification Checkpoints

Run the automated verification suite:
```bash
pytest tests/test_stage_05.py -v
```

### Checkpoint Verifications:
1. **T2VA End-to-End Generation:**
   - Seed: `"A detective walks into an abandoned warehouse in the rain"`
   - Assert prompt output contains exactly 3 fields:
     - `integrated_multimodal_description: [Shot 1] Live-action, cinematic...`
     - `overall_soundscape: N/A` (under `dialogue_only`)
     - `non_diegetic_music: N/A`
2. **Prose Fallback Verification:**
   - Force mock Ollama to fail on `prose_writer`:
   - Assert clip status is `preflight` with `prompts.prose_fallback == 1`.
   - Assert all planned dialogue placeholders `{{L1}}` are stitched into the fallback prose.
3. **Stage 0 Zero-Ollama Guard:**
   - Submit clip with Kannada line written in English letters (`"Bega ba"`):
   - Assert HTTP 422 validation error returned.
   - Assert mock Ollama request count is strictly 0.
