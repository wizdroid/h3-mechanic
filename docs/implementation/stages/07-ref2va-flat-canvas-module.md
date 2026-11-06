# Stage 07: REF2VA Flat Single-Canvas & Many-to-Many Linking

**Milestone:** M6  
**Specification Reference:** [`specification-0.3.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.3.md) §§4.4.6, 6.1, 6.4, 7.4, 7.6, 8.3–8.6, Appendix A.9  
**Key Acceptance Criteria:** A-05, A-11, A-24, A-38, A-39, A-42, A-43, A-45  

---

## 1. Stage Overview & Scope

Implement the complete **REF2VA (Full-Reference Mode)** module. This stage incorporates the major Version 0.3 architectural simplifications: replacing the 4-step wizard stepper with a flat single-canvas layout, treating reference tokens as lightweight metadata with optional dimensions, and enabling flexible many-to-many Subject-to-Picture mapping (0 pictures, 1 picture, or multiple pictures).

### Deliverables:
1. `app/web/js/modes/ref2va.js`: Flat single-canvas UI controller displaying all four cards simultaneously without step gating or progression locks:
   - Card 1: **Reference Tokens Card** (`<Picture N>`, `<Audio N>`, `<Video N>`).
   - Card 2: **Subjects & Picture Mapping Card** (Multi-select picture linking chips with role assignments).
   - Card 3: **Shot Editor & Dialogue Card** (Shots, camera moves, dialogue lines, audio timbre links).
   - Card 4: **Action Bar & Retention Analysis Card** (Preflight checklist preview, Generate trigger, Retention table, Export).
2. `app/api/ref2va_routes.py`: Backend route handlers orchestrating the staged REF2VA pipeline:
   - Deterministic `subject_defs` builder (§8.3).
   - `shot_writer` stage (§8.4).
   - Code-derived task type prefix & `summary_writer` (§8.5).
   - Retention row synchronizer & `retention_writer` (§8.6).
   - Six-section renderer assembly (§7.6).
3. `tests/test_stage_07.py`: Test suite verifying 0/1/multi-picture subject generation, PLATES attach order, task type triggers, retention analysis formatting, and 6-section layout.

---

## 2. Step-by-Step Implementation Instructions

### Step 7.1: REF2VA Flat Single-Canvas Interface (`app/web/js/modes/ref2va.js`)
Build the flat unified canvas per §4.4.6:
- **Card 1: Reference Tokens:**
  - Token rows displaying kind (`image`, `video`, `audio`), auto-assigned label (`<Picture 1>`, `<Audio 1>`, `<Video 1>`), optional caption, optional source filename, and duration/dimension inputs.
  - Drag-and-drop or position up/down reordering using the positive offset shift transaction (§6.4).
  - Live budget counters: images (max 9), videos (max 3), audio (max 3), files (max 12).
- **Card 2: Subjects & Picture Mapping:**
  - Add/remove subjects with role dropdown (person, character, location, prop, outfit, etc.), grammatical pronoun (`his`/`her`/`its`), short role noun (`officer`), outfit noun (`uniform`), optional appositive (`a convict`), and feature list.
  - Multi-select picture link chips:
    - 0 pictures linked: text-only description mode.
    - 1 picture linked: standard identity anchor.
    - Multiple pictures linked: e.g. `<Picture 1>` (identity_anchor) + `<Picture 2>` (outfit).
  - Shot anchor dropdown for composition, framing, and frame roles (`anchor_shot_id`).
- **Card 3: Shot Editor & Dialogue:**
  - Add/remove shots: start time `MM:SS.mmm` (Shot 1 locked to 0.00s), size, angle, official camera move with landing, pacing (`silent` or `action`).
  - Dialogue lines: speaker selector, audio timbre link (`audio_reference_id`), delivery, native script, cross-cut flag with destination shot selector.
- **Card 4: Action Bar & Retention:**
  - Auto-synchronized retention table: subject entries, anchor picture entries, video entries, audio entries.
  - Marker dropdowns (`fully_preserved`, `partially_preserved`, `attribute_transfer`, `weak_reference`, `fully_copy`, `reference`).
  - Editable reason inputs with LLM generation helper.

### Step 7.2: Deterministic Subject Definitions Compiler
Integrate `app/engine/subject_builder.py` into the REF2VA pipeline to emit:
1. **Person Subjects:**
   - 0 pictures: `<Subject 1> is the officer, a prison guard, with his appearance, facial features, build, and complete uniform defined by text alone.`
   - 1 picture: `<Subject 1> is the officer in <Picture 1>, a prison guard, with his face, hair, build, and complete uniform taken exactly from the reference.`
   - Multiple pictures: `<Subject 1> is the officer with his face, hair, and build taken from <Picture 1>, a prison guard, and his complete uniform taken from <Picture 2>.`
2. **Location Subjects:**
   `<Subject 3> is the prison corridor in <Picture 3>, including its walls, floor, cell doors, and layout exactly as shown.`
3. **Picture Anchor Lines:**
   `<Picture 4> is the composition anchor for [Shot 1], defining the camera position, viewpoint, and framing.`
4. **Audio Lines:**
   `<Audio 1> is the voice-timbre reference for <Subject 1> (S1).`

### Step 7.3: Task Types & Summary Writer (`app/llm/pipeline.py`)
- Code-derived task type prefix (§8.5, Appendix A.9):
  - Guidance reference present ⇒ `reference generation`.
  - Frame / composition anchor present ⇒ `keyframe completion`.
  - Audio used only for timbre ⇒ `audio reference`.
  - User-selected flags: `video editing`, `video continuation`, `audio reuse`.
- `summary_writer`: LLM receives labels and plan; outputs summary paragraph only.
- Renderer prepends bracket prefix, e.g. `[reference generation + audio reference]`.
- For `video editing`: renderer prepends `The target video is an edited version of <Video K>.`.

### Step 7.4: Retention Writer & Assembly
- Retention synchronizer creates rows for all subjects, picture anchors, videos, and audios.
- `retention_writer` fills missing reasons (max 25 words, no `(Sx)` tags).
- Six-Section Assembly (§7.6):
  1. `subject_definitions:`
  2. `summary:`
  3. `retention_analysis:`
  4. `detailed_description:` (opens with `The target video is ...` style sentence, then `[Shot N]` lines).
  5. `overall_soundscape:`
  6. `non_diegetic_music:`

---

## 3. Calibrated Master Prompt for Stage 07

```text
You are an expert full-stack engineer implementing Stage 07 (REF2VA Flat Single-Canvas & Many-to-Many Linking) of H3 Prompt Studio strictly according to docs/specifications/specification-0.3.md.

Task:
Build the flat single-canvas REF2VA interface, backend pipeline, deterministic subject definition compiler with S-03 many-to-many picture linking, summary writer, retention writer, and six-section renderer.

Strict Boundaries:
1. Flat Single-Canvas UI (§4.4.6, Criterion A-24):
   - NO wizard stepper or step-locking gating. All cards (Reference Tokens, Subjects & Picture Mapping, Shot Editor, Action Bar) must be visible simultaneously on a single unified canvas.
   - Database clips.wizard_step remains 1 for schema backward compatibility.
2. Lightweight Reference Tokens (S-02 / §6.1, §6.4, PF-20, Criterion A-11):
   - Image width_px and height_px are optional metadata; dimensions outside 256–5760 px emit advisory warnings, not blocking errors.
   - Strictly enforce hard limits: ≤ 9 images, ≤ 3 videos, ≤ 3 audio, ≤ 12 files; durations 2–15s.
3. Many-to-Many Subject-to-Picture Linking (S-03 / §6.1, §6.4, §8.3, Appendix A.9):
   - Support 0 pictures linked (text-only formula).
   - Support 1 picture linked (identity anchor formula).
   - Support multiple pictures linked (e.g. face anchor from Picture 1 and outfit from Picture 2).
   - Picture anchor roles (first_frame, keyframe, last_frame, composition_anchor, framing_reference) emit separate Picture anchor lines.
4. Output Layout Contract (§7.6, PF-01, Criterion A-38):
   - Exactly six sections in order: subject_definitions, summary, retention_analysis, detailed_description, overall_soundscape, non_diegetic_music.
   - Section headers stand alone on their own lines.
   - detailed_description starts with style sentence "The target video is ...", followed by [Shot N] on separate lines.
   - Cut wording is strictly "the camera cuts to".
   - Destination cross-cut prefix placed after cut header for N > 1 (S-04).
5. Tests:
   - Create tests/test_stage_07.py verifying:
     * Full REF2VA generation with 3 images, 1 audio, and 2 subjects (one with dual picture links).
     * Rejection of > 9 images or > 3 videos (422 error).
     * Formatting of 6 sections and PLATES.txt attach order.
     * video editing summary opening prefix.
```

---

## 4. Integrated Verification Checkpoints

Run the automated verification suite:
```bash
pytest tests/test_stage_07.py -v
```

### Checkpoint Verifications:
1. **Many-to-Many Picture Link Compilation:**
   - Link `<Picture 1>` (identity_anchor) and `<Picture 2>` (outfit) to `<Subject 1>`:
   - Assert `subject_definitions` line matches:
     `<Subject 1> is the officer with his face, hair, and build taken from <Picture 1> and his complete uniform taken from <Picture 2>.`
2. **0-Picture Subject Compilation:**
   - Define `<Subject 2>` with 0 linked pictures:
   - Assert `subject_definitions` line matches:
     `<Subject 2> is the informant with his appearance, facial features, build, and complete outfit defined by text alone.`
3. **Six-Section Format Integrity:**
   - Verify rendered prompt against PF-01:
     - Section headers alone on lines with colons.
     - `detailed_description` starts with `The target video is...` before `[Shot 1]`.
     - Cut times match `At MM:SS.mmm, the camera cuts to`.
4. **PLATES Attach Order File:**
   - Export clip → Assert `clip-<NN>-PLATES.txt` contains references in row order with exact roles.
