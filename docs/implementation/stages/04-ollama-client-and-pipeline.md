# Stage 04: Ollama Client, Concurrency Lock & Pipeline Engine

**Milestone:** M3  
**Specification Reference:** [`specification-0.3.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.3.md) §§4.4.7, 5.4, 5.5, 5.6, 8.0, 8.1–8.7  
**Key Acceptance Criteria:** A-09, A-13, A-14, A-15, A-16, A-30, A-32, A-33, A-37  

---

## 1. Stage Overview & Scope

Implement the local LLM integration layer via Ollama, the process-wide execution lock, structured JSON decoding with schema fallback, the multi-stage pipeline runner, and the preflight repair loop.

### Deliverables:
1. `app/llm/client.py`: Asynchronous Ollama HTTP client (tags prefetch, model introspection, generate requests, structured output decoding, warmup calls, cancellation).
2. `app/llm/lock.py`: Global single-flight `asyncio.Lock` managing `/generate`, `/fix`, and `/variations` requests (HTTP 409 `busy`). Includes startup crash recovery to reset stuck `generating` clips to `draft`.
3. `app/llm/prompt_bank.py`: Parameterized meta-prompt templates defined in §8.
4. `app/llm/pipeline.py`: Staged pipeline runner:
   - NDJSON streaming events (`stage_start`, `stage_done`, `stage_retry`, `violations`, `done`, `error`).
   - One structural retry per stage with temperature bumped by +0.1 and seed perturbed: `(seed + 1) mod 4294967296`.
   - Strict enforcement of worst-case LLM call counts ($\le 6$ for T2VA/frames, $\le 8$ for REF2VA).
5. `app/llm/fixer.py`: Preflight repair loop validating placeholder preservation before accepting fixer outputs.
6. `app/api/llm_routes.py`: API routes for models, generation, cancellation, warmup, and fixer.
7. `tests/test_stage_04.py`: Comprehensive test suite using `httpx.MockTransport` verifying mock Ollama interactions, structured output schema fallbacks, retry budgets, lock concurrency, and fixer integrity.

---

## 2. Step-by-Step Implementation Instructions

### Step 4.1: Ollama HTTP Client (`app/llm/client.py`)
- Endpoints:
  - `GET /api/tags`: List local models.
  - `POST /api/show`: Model metadata (family, parameter size, quantization, context length).
  - `POST /api/generate`: Prompt execution.
- Structured Decoding:
  - Send `format: <JSON Schema>` for JSON stages (`seed_elaboration`, `frame_action_elaboration`, `retention_writer`).
  - If Ollama rejects the schema, gracefully fall back to `format: "json"`.
  - Validate response in Python with `jsonschema` against the stage schema.
- Context & Budget Pre-flight:
  - Estimate prompt tokens: `len(prompt) / 3.2`.
  - Enforce `estimated_tokens + num_predict <= 0.9 * num_ctx`; fail fast if exceeded.
- Timeouts & Keep-Alive:
  - Connect timeout: 5s. Read timeout: Settings `timeout_s` (default 120s).
  - Send `keep_alive: "10m"`.

### Step 4.2: Concurrency Lock & Crash Recovery (`app/llm/lock.py`)
- Process-wide `asyncio.Lock`.
- When acquired: update active clip `status = 'generating'`.
- If a second request arrives while locked: return HTTP 409 `{"error":{"code":"busy","active_clip_id":<id>}}`.
- Release lock in `finally` block on completion, error, cancel, or client disconnect.
- Startup Hook: On application boot, run `UPDATE clips SET status = 'draft' WHERE status = 'generating'` to recover from ungraceful crashes.

### Step 4.3: Meta-Prompt Bank (`app/llm/prompt_bank.py`)
Implement the exact templates specified in §8:
- `seed_elaboration` (T2VA plan JSON).
- `frame_action_elaboration` (Frame modes motion JSON).
- `prose_writer` (T2VA & frame shot prose).
- `shot_writer` (REF2VA detailed description prose).
- `summary_writer` (REF2VA summary paragraph).
- `retention_writer` (REF2VA retention reasons JSON).
- `preflight_fixer` (Targeted template rewrite for fixable violations).
- `safer_framing` (Alternative camera framing variation).

### Step 4.4: Staged Pipeline Runner (`app/llm/pipeline.py`)
- Execute stages in order.
- Stream progress via NDJSON lines:
  ```json
  {"event":"stage_start","stage":"seed_elaboration","ms":0}
  {"event":"stage_done","stage":"seed_elaboration","ms":1450}
  ```
- Structural Failure Retry:
  - Triggered on JSON schema mismatch, empty output, truncated output (`done_reason == "length"`), or placeholder violation.
  - Retry **once** with `temperature = temperature + 0.1` and `seed = (seed + 1) % 4294967296`.
  - If retry fails, stop pipeline, set clip `status = 'failed'`, preserve partial results.
- Hard Call Budget Caps (§5.5, Criterion A-32):
  - T2VA / Frame modes: Plan (1+1) + Prose (1+1) + Fixer (2) = **$\le 6$ calls**.
  - REF2VA: Shot (1+1) + Summary (1+1) + Retention (1+1) + Fixer (2) = **$\le 8$ calls** (`subject_defs` is deterministic).

### Step 4.5: Preflight Repair Loop (`app/llm/fixer.py`)
Per §5.5 & §9.3:
1. Run deterministic autofix first (Pass 1–5).
2. If remaining errors have `fixable == false`: stop and block export; do not call LLM.
3. If all blocking errors are `fixable == true`: call `preflight_fixer` with violation list.
4. **Integrity Guard:** Fixer output must preserve the exact multiset of `{{Lk}}` and `{{Tm}}` tokens. If any placeholder was lost, renamed, or added, discard the fixer response and increment retry counter.
5. Re-render, re-run preflight. Stop after $N$ retries (default 2).

---

## 3. Calibrated Master Prompt for Stage 04

```text
You are an expert systems engineer implementing Stage 04 (Ollama Client, Concurrency Lock & Pipeline Engine) of H3 Prompt Studio strictly according to docs/specifications/specification-0.3.md.

Task:
Implement the Ollama HTTP client, single-flight process lock, prompt templates, multi-stage pipeline runner, and preflight repair loop.

Strict Boundaries:
1. Ollama Client (§5.4):
   - Asynchronous httpx client for /api/tags, /api/show, /api/generate.
   - Structured JSON outputs: send stage JSON Schema in format; fall back to "json" string if rejected by server; validate response with Python jsonschema.
   - Token budget check: fail fast if estimated prompt tokens + num_predict > 0.9 * num_ctx.
2. Concurrency Lock (§5.5, §5.7, Criterion A-30):
   - Single process-wide asyncio.Lock for all generation/fix/variation endpoints.
   - Return HTTP 409 code "busy" with active_clip_id when held.
   - Ensure try/finally releases lock on cancel, timeout, error, or disconnect.
   - Startup recovery resets any clips with status == 'generating' to 'draft'.
3. Pipeline Runner (§5.5):
   - Stream progress using NDJSON (application/x-ndjson).
   - Structural failures trigger at most ONE retry with temperature +0.1 and perturbed seed.
   - Worst-case call counts strictly capped: ≤ 6 for T2VA/frames, ≤ 8 for REF2VA.
4. Preflight Fixer Loop (§5.5, §8.0, §9.3):
   - Run deterministic autofix before invoking LLM fixer.
   - Reject fixer output if any {{Lk}} or {{Tm}} placeholder is dropped, altered, or added.
   - Up to max_fixer_retries (default 2).
5. Tests:
   - Create tests/test_stage_04.py using httpx.MockTransport simulating:
     * Successful structured generation.
     * Schema validation failure triggering single retry with bumped temperature/seed.
     * 409 busy response when lock is occupied.
     * Crash recovery on startup.
     * Worst-case call budget ceiling compliance.
     * Discarding fixer outputs that tamper with placeholders.

Do not write HTML/CSS front-end code in this stage.
```

---

## 4. Integrated Verification Checkpoints

Run the automated verification suite:
```bash
pytest tests/test_stage_04.py -v
```

### Checkpoint Verifications:
1. **Concurrency Lock Test:**
   - Launch long-running simulated `/generate`.
   - Issue second request to `/generate` on another clip → Assert HTTP 409 with `"code":"busy"`.
2. **Schema Retry & Recovery Test:**
   - Mock Ollama returning invalid JSON on attempt 1, valid JSON on attempt 2:
   - Assert attempt 2 uses `temperature = 0.3` and `seed = (seed + 1)`.
   - Assert pipeline completes successfully.
3. **Worst-Case Budget Cap Test:**
   - Mock Ollama failing continuously on T2VA:
   - Assert total requests to mock Ollama does not exceed 6 calls.
4. **Fixer Placeholder Tamper Rejection:**
   - Mock fixer returning text with `{{L1}}` replaced with raw text:
   - Assert fixer output is discarded and retry count increments.
