# Stage 08: Settings, System Hardening & Final Acceptance (Last Stage)

**Milestone:** M7  
**Specification Reference:** [`specification-0.3.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.3.md) §§4.4.7, 5.6, 5.7, 7.5, 10.2, 11.1–11.2, 13, 14  
**Key Acceptance Criteria:** A-21, A-25, A-26, A-28, A-31, A-36, A-44, A-47  

---

## 1. Stage Overview & Scope

The final development stage delivers the complete Settings module, theme switcher, voice library browser, variations panel ("Safer framing"), optimistic concurrency protection, end-to-end documentation (`README.md` and `USER_GUIDE.md`), and the complete automated acceptance test suite mapping and certifying all 49 Acceptance Criteria (A-01 through A-49).

### Deliverables:
1. `app/web/js/settings.js`: Settings view controller:
   - Ollama endpoint configuration with `[Test]` connection button.
   - Drafter model dropdown populated from `GET /api/models` (prefetched Ollama tags).
   - Drafter metadata viewer (family, parameter size, quantization, context length).
   - Generation parameters: temperature (0.2), num_ctx (8192), timeout_s (120), keep_alive (10m), seed mode (auto/fixed), max fixer retries (2).
   - H3 video model toggle (`MiniMax-H3` vs `MiniMax-H3-Max`).
   - Default project and clip settings.
   - Export directory path validation.
   - Customizable listen port (integer 1–65535, default 9013).
   - Theme switcher: Nord Dark, Nord Coloured, Nord Light.
2. `app/web/js/voice_library.js`: Voice library modal / inspector (F1–F10, M1–M11, K1–K2) with search and audio previews.
3. `app/api/variations_routes.py`: "Safer framing" alternative generator:
   - Max 1 variation per draft; second request returns HTTP 409 `validation`.
   - `/select` endpoint choosing draft or variation as export source.
4. Optimistic Concurrency Engine:
   - `If-Match: <revision>` enforcement on all mutating routes.
   - Mismatch returns HTTP 412 `precondition` with prompt to reload.
5. `README.md` & `USER_GUIDE.md`: Comprehensive user and setup documentation matching §11.
6. `tests/ACCEPTANCE.md`: Full traceability matrix mapping all 49 criteria (A-01 to A-49) to automated tests.
7. `tests/test_acceptance.py`: End-to-end test suite running the entire acceptance battery.

---

## 2. Step-by-Step Implementation Instructions

### Step 8.1: Settings Module & Persistence (`app/web/js/settings.js`)
- Persist settings in SQLite `settings` table (§7.5).
- Endpoint `GET /api/models`: Calls Ollama `GET /api/tags` and caches model list.
- Endpoint `GET /api/models/{name}`: Calls Ollama `POST /api/show` to retrieve model details.
- H3 Video Model Constraints (§6.3, Criterion A-26):
  - When switching to `MiniMax-H3`: clamp duration 4–15s; allow resolutions `768P`, `2K`.
  - When switching to `MiniMax-H3-Max`: clamp duration 5–15s; allow resolutions `480P`, `768P`.
- Export Directory Validator:
  - User-provided path is verified via `Path.resolve()`. Must exist and be writable; returns HTTP 422 if invalid.
- Dynamic Listen Port (§5.7, Criterion A-49):
  - Setting `listen_port` (1–65535). Saved value applies on next process start.

### Step 8.2: Voice Library Inspector (`app/web/js/voice_library.js`)
- Modal/panel populated from `GET /api/voices`:
  - Female: F1 through F10.
  - Male: M1 through M11.
  - Kid: K1 and K2.
- Display voice ID, voice phrase description, gender, age tier, and suggested delivery styles.
- One-click copy or insert into speaker definition.

### Step 8.3: Variations ("Safer Framing") (`app/api/variations_routes.py`)
Per §5.5 & §10.2:
- Action "Safer framing" generates one alternative camera framing prompt from the same plan.
- At most 2 prompts per clip (draft + 1 variation).
- Attempting to generate a second variation returns HTTP 409 `{"error":{"code":"validation","message":"Only one safer framing variation permitted."}}`.
- `POST /api/clips/{id}/select` allows selecting which variation becomes active for preflight and export.

### Step 8.4: Optimistic Concurrency Protection (§5.7, Criterion A-36)
- Increment `clips.revision` (+1) on every clip or child row update.
- Mutating endpoints (`PUT /api/clips/{id}`, `POST /generate`, `POST /export`, etc.) inspect `If-Match: <revision>`.
- If request revision != database revision: return HTTP 412 `precondition` with current revision.
- Front end displays notification: "Clip was modified in another tab. Reload to sync."

### Step 8.5: End-to-End Documentation (`README.md` & `USER_GUIDE.md`)
Write complete documentation according to the §11 plan:
- **`README.md`:** Installation, prerequisites (Python 3.10+, Ollama), setup in virtual environment, configuration, quick-start guide, file structure, troubleshooting.
- **`USER_GUIDE.md`:**
  - Novice walkthrough: first launch, T2VA seed, I2VA frame, reading preflight status badges.
  - Advanced guide: REF2VA flat canvas guide, reference linking (0, 1, or multiple pictures), audio timbre vs reuse, video pacing and continuation, camera moves, mood word rules, PLATES handoff to ComfyUI.

### Step 8.6: Final Acceptance Test Suite (`tests/ACCEPTANCE.md`)
Create `tests/ACCEPTANCE.md` establishing a complete audit trail:
- Maps all criteria A-01 through A-49 to automated pytest functions in `tests/test_acceptance.py`.
- Run the full test suite and verify 100% pass rate.

---

## 3. Calibrated Master Prompt for Stage 08 (Last Stage)

```text
You are an expert systems engineer implementing Stage 08 (Settings, System Hardening & Final Acceptance) of H3 Prompt Studio strictly according to docs/specifications/specification-0.3.md.

Task:
Build the Settings module, theme switcher, voice library inspector, safer framing variations, optimistic concurrency hardening, user documentation, and the complete 49-point acceptance test suite.

Strict Boundaries:
1. Settings Module (§4.4.7, §7.5, Criterion A-13, A-14, A-15, A-26):
   - Prefetch Ollama tags via GET /api/models.
   - Enforce video model matrix: MiniMax-H3 (4–15s, 768P/2K), MiniMax-H3-Max (5–15s, 480P/768P).
   - Dynamic port resolution (§5.7): H3_PORT -> settings listen_port -> 9013.
2. Variations ("Safer Framing") (§10.2, Criterion A-28):
   - Exactly one safer framing variation per draft. A third prompt attempt returns HTTP 409 validation.
   - /select endpoint allows switching selected prompt for export.
3. Optimistic Concurrency (§5.7, Criterion A-36):
   - Require If-Match header on mutating routes. Return 412 precondition if mismatched.
4. Voice Library & Themes:
   - Inspect voices F1–F10, M1–M11, K1–K2 (§A.7).
   - Theme toggle between nord-dark, nord-coloured, and nord-light without page reload.
5. Documentation (§11.1, §11.2, Criterion A-25):
   - Write comprehensive README.md and USER_GUIDE.md.
6. Final Acceptance Testing (§13, §14, Criteria A-01 through A-49):
   - Create tests/ACCEPTANCE.md mapping all 49 acceptance criteria to tests.
   - Create tests/test_acceptance.py executing tests for every criterion:
     * A-01 to A-07 (Mode behaviors)
     * A-08 to A-12 (Validation and limits)
     * A-13 to A-16 (Ollama integration)
     * A-17 to A-21 (Export and data)
     * A-22 to A-28 (UX and docs)
     * A-29 to A-49 (Robustness and pipeline integrity)
   - Ensure 100% pass rate across the full test battery.
```

---

## 4. Integrated Verification Checkpoints

Run the complete acceptance test suite:
```bash
pytest tests/test_acceptance.py -v
```

### Checkpoint Verifications:
1. **Full Acceptance Battery:**
   - Execute: `pytest tests/ -v`
   - Assert all 49 acceptance criteria tests in `tests/ACCEPTANCE.md` pass with 0 failures.
2. **Safer Framing Limit:**
   - Generate draft prompt.
   - Call `POST /api/clips/{id}/variations` → Assert second variation created.
   - Call `POST /api/clips/{id}/variations` again → Assert HTTP 409 rejected.
3. **Optimistic Concurrency Protection:**
   - Client A reads clip at `revision = 1`.
   - Client B updates clip to `revision = 2`.
   - Client A attempts update sending `If-Match: 1` → Assert HTTP 412 `precondition`.
4. **Final Health & Specification Check:**
   - `GET /api/health` → Assert `"specification_version":"0.3"`, `"status":"ok"`.
