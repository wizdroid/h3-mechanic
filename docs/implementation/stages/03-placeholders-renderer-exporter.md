# Stage 03: Placeholders, Deterministic Renderer & Atomic Exporter

**Milestone:** M2  
**Specification Reference:** [`specification-0.3.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.3.md) §§8.0, 8.1b, 8.3, 8.7, 10.1, 10.2, Appendix A  
**Key Acceptance Criteria:** A-06, A-17, A-18, A-19, A-40, A-46  

---

## 1. Stage Overview & Scope

Implement the core deterministic rendering and export engines. This stage guarantees that no sensitive tokens (dialogue scripts, voice phrases, speaker IDs, instruction lines, or subject definitions) are left to an LLM to generate or corrupt. It also implements atomic, race-free file exports and export collision detection keyed on integer numeric clip numbers.

### Deliverables:
1. `app/engine/placeholders.py`: Placeholder generator (`{{Lk}}`, `{{Tm}}`), template integrity checker, and structured plan generator.
2. `app/engine/subject_builder.py`: Deterministic REF2VA `subject_definitions` compiler implementing the S-03 formulas for 0, 1, or multiple linked pictures.
3. `app/engine/renderer.py`: Deterministic prompt assembler:
   - Instruction lines for I2VA, FL2VA, and L2VA with exact formatting and computed `N` and `S.SS`.
   - Speech sentence expansion (`{{Lk}}`) with voice timbre, accents, delivery manners, native script spans, and lip closure sentences.
   - S-04 cross-cut destination placement after the cut header for $N > 1$.
   - S-05 fallback prose stitcher (`fallback_prose`) preserving all dialogue/text placeholders without omission.
   - Dialogue-only house sentence insertion.
4. `app/engine/exporter.py`: Atomic export writer:
   - Collision detection on integer `NN` alone (S-07), matching unpadded and zero-padded files.
   - Atomic file creation via temporary file and `os.link` / `os.replace`.
   - `clip-<NN>-<D>s.txt` prompt file generator.
   - `clip-<NN>-PLATES.txt` companion file generator.
   - Full JSON snapshot backups (`data/backups/clip-<id>-<ts>.json`) pruned to the last 5 per clip.
5. `app/api/export_routes.py`: Endpoints for `POST /api/clips/{id}/export` and clipboard copy helper.
6. `tests/test_stage_03.py`: Golden render tests, placeholder expansion tests, atomic collision test suite.

---

## 2. Step-by-Step Implementation Instructions

### Step 3.1: Placeholder Protocol (`app/engine/placeholders.py`)
- Number dialogue lines $k = 1..n$ by `(shot.start_ms, line_order, id)`. Emit `{{Lk}}` token stubs.
- Number on-screen texts by `onscreen_texts.ordinal` as `{{Tm}}`.
- Template Integrity Validator:
  - Check every `{{Lk}}` appears exactly once and the sequence is strictly increasing.
  - In REF2VA, verify `{{Lk}}` sits inside the owning shot.
  - Confirm no `{{V:` tokens and no dangling `{{"` remain.

### Step 3.2: Deterministic Subject Definition Builder (`app/engine/subject_builder.py`)
Compile `subject_definitions` per §8.3 and Appendix A.9 without any LLM call:
- **0 Pictures Linked:**
  `<Subject N> is the {role_phrase}[, {appositive},] with {pronoun} appearance, facial features, build, and complete {outfit_noun} defined by text alone.`
- **1 Picture Linked:**
  `<Subject N> is the {role_phrase} in <Picture M>[, {appositive},] with {pronoun} face, hair, build, and complete {outfit_noun} taken exactly from the reference.`
- **Multiple Pictures Linked:**
  `<Subject N> is the {role_phrase} with {pronoun} face, hair, and build taken from <Picture M>[, {appositive},] and {pronoun} complete {outfit_noun} taken from <Picture P>.`
- **Picture Anchor Lines:**
  `<Picture N> is the {role} for [Shot X], defining {defines_text}.`
- **Audio References:**
  `<Audio N> is the voice-timbre reference for <Subject N> (Sx).`

### Step 3.3: Final Assembler & Renderer (`app/engine/renderer.py`)
Implement the deterministic assembler (§8.0, §8.7):
- Instruction lines:
  - I2VA: `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`
  - FL2VA: `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.` (no angle/square brackets; em dash U+2014; `S.SS = str(duration_s) + ".00"`).
  - L2VA: `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.`
- Expand `{{Lk}}` into the 8-component speech sentence:
  1. Speaker reference (`<Subject N>` or `The {persona}`).
  2. Speaker tag (`(S1)` or `(S1,S2)`).
  3. Verb (from delivery table, e.g. `whispers`, or `says in an off-screen voiceover`).
  4. Voice phrase (library phrase or `in the voice timbre referenced from <Audio N>`).
  5. Accent clause (`, with a natural Bengaluru urban accent`).
  6. Delivery manner (`, through gritted teeth`).
  7. Spoken dialogue (`<d>[{Language}] {normalised text}</d>`), with `<scenetrans>` immediately before `<d>` if cross-cut, and `<cutoff>` if cutoff.
  8. Lip closure sentence: Voiceover: ` while {pronoun} lips remain completely closed.`; regular: `He/She/It closes his/her/its lips.` or `Both speakers close their lips.`
- Cross-Cut Destination Prefix:
  - For destination Shot 1 ($N=1$): prefix shot prose with `<scenetrans> The audio continues seamlessly across the cut. `.
  - For destination Shot $N > 1$: place immediately AFTER cut header: `[Shot N] At MM:SS.mmm, the camera cuts to <scenetrans> The audio continues seamlessly across the cut. `.
- Fallback Prose Stitcher (`fallback_prose`):
  - If prose model fails, stitch structured plan shots directly.
  - S-05 Guarantee: Must insert every planned `{{Lk}}` and `{{Tm}}` placeholder for that shot into the stitched sentence.
- House Audio Sentence:
  - Insert `The audio contains only the spoken dialogue, with no background music, no ambience, and no sound effects.` at the exact §7.6 position under `dialogue_only`.

### Step 3.4: Atomic Exporter (`app/engine/exporter.py`)
Per §10.1 & §10.2:
- **Integer NN Collision:** Extract integer `int(m.group(1))` from existing `clip-(\d+)-.*` files. If any file matches `int(NN)`, trigger collision policy:
  - `auto_increment`: compute `max(existing_NN) + 1`.
  - `prompt_override`: return HTTP 409 `{"error":{"code":"collision","message":"Clip number NN collides with: ..."}}` unless `overwrite == True`.
- **Atomic File Writing:** Write content to temporary file `data/exports/.tmp_clip_<NN>_<ts>`.
  - If `overwrite == False`: `os.link(temp, target_path)` then delete temp (or `open(target, "x")`).
  - If `overwrite == True`: `os.replace(temp, target_path)`.
- **PLATES File (REF2VA):** Write `clip-<NN>-PLATES.txt` with one line per reference in attach order:
  `<Label>: <filename-or-MISSING> — <role>: <caption>` (em dash U+2014).
- **Snapshot Backup & Pruning:** Save clip snapshot to `data/backups/clip-<id>-<ts>.json`. Prune to retain only the last 5 snapshots per clip.

---

## 3. Calibrated Master Prompt for Stage 03

```text
You are an expert systems engineer implementing Stage 03 (Placeholders, Deterministic Renderer & Atomic Exporter) of H3 Prompt Studio strictly according to docs/specifications/specification-0.3.md.

Task:
Implement the placeholder protocol, subject definitions builder, deterministic prompt renderer, atomic exporter, PLATES file generator, and snapshot backup manager.

Strict Boundaries:
1. Placeholder Protocol (§8.0):
   - Dialogue lines are stubs {{Lk}}; on-screen texts are {{Tm}}. The LLM never sees or copies native scripts, voice phrases, or speaker IDs.
2. Deterministic Subject Definitions (S-03 / §8.3 / Appendix A.9):
   - Implement deterministic generation supporting 0 pictures (text-only), 1 picture (identity anchor), and multiple pictures (face from Picture M, outfit from Picture P).
   - Never call an LLM to generate subject definitions.
3. Deterministic Renderer (§8.0, §8.7):
   - Expand {{Lk}} to the exact 8-part speech sentence with lip closure and voice phrases.
   - S-04 Safeguard: For destination shots N > 1, place the cross-cut prefix immediately after the cut header:
     "[Shot N] At MM:SS.mmm, the camera cuts to <scenetrans> The audio continues seamlessly across the cut. "
   - S-05 Safeguard: In fallback_prose (§8.1b), stitch the planned shots while guaranteeing that all {{Lk}} and {{Tm}} placeholders for that shot are preserved without loss.
   - Insert the dialogue-only house audio sentence at the exact §7.6 position.
4. Atomic Exporter (S-07 / §10.1, §10.2):
   - Collision detection MUST be keyed on integer NN alone: regex clip-(\d+)-.* compared as int(group(1)) == int(NN). Both clip-1-8s.txt and clip-01-8s.txt collide.
   - Return HTTP 409 code "collision" on conflicts unless overwrite: true.
   - Perform atomic file writes using temp file + os.link / os.replace.
   - Generate clip-<NN>-PLATES.txt for REF2VA with U+2014 em dashes.
   - Save JSON snapshots to data/backups/ and prune to the last 5 per clip.
5. Tests:
   - Create tests/test_stage_03.py with golden render fixtures (I2VA, FL2VA, L2VA, Kannada dialogue expansion, cross-cut destination placement, PLATES attach order, collision detection on padded/unpadded NN, atomic export simulation).

Do not implement UI frontend views or direct Ollama HTTP requests in this stage.
```

---

## 4. Integrated Verification Checkpoints

Run the automated verification suite:
```bash
pytest tests/test_stage_03.py -v
```

### Checkpoint Verifications:
1. **Golden Instruction Line Tests:**
   - FL2VA with 2 shots, 8s duration:
     Assert instruction line equals `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 2) aligns with the 8.00-second mark of the target video.` (byte-exact, no angle brackets).
2. **Cross-Cut Destination Prefix:**
   - Cross-cut line in Shot 1 targeting Shot 2 at 3.5s:
     Assert Shot 2 starts with `[Shot 2] At 00:03.500, the camera cuts to <scenetrans> The audio continues seamlessly across the cut. `.
3. **Collision Detection on Integer NN:**
   - Create existing file `clip-01-8s.txt`.
   - Attempt export with `clip_number = 1` and `duration_s = 10` without overwrite:
     Assert HTTP 409 `{"error":{"code":"collision",...}}`.
4. **PLATES File Verification:**
   - Attach image 1, audio 1, image 2.
   - Assert `clip-<NN>-PLATES.txt` lists rows in attach order with `<Label>: <source> — <role>: <caption>`.
