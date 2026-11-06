# H3 Prompt Studio — Experience Specification

**Version:** 0.3 (Final Locked)
**Status:** Final certified implementation contract, superseding all previous revisions (v0.2, v0.1, v1.6). Locked as the sole authoritative product specification. The listen port is customizable (§5.7). The host stays `127.0.0.1`. The default port stays `9013`. No Section 12 or Section 16 default was changed.
**Stack:** Python 3.10+ back-end (FastAPI · Uvicorn · httpx · jsonschema · stdlib `sqlite3`) · Local LLM via Ollama · SQLite + JSON in designated data directories · Nord-themed vanilla JS web UI · `127.0.0.1` and a configurable port (default `9013`)
**Normative authority:** this specification alone. Its sections and Appendix A define every H3 mode, output shape, limit, vocabulary, default, and validation rule required by v1. §17 gives the absolute paths those rules use on this machine. Implementation resources may split the Appendix A values into code or JSON files under the §17 runtime paths. The process must not fetch, load, or checksum the §17.3 reference files. Older revision notes record what changed. If a revision note disagrees with the body, the body wins.

**Revision 1.1:** H3/H3-Max limits are separate from the Ollama drafter. FL2VA may be one shot. Image dimensions are typed fields. Export duration is written into the filename. Style is a selected opening. Dialogue stays verbatim. Subject lines use deterministic formulas. Picture roles are stored per picture. Clipboard text is the raw prompt. Task-type prefixes are bracketed. Custom sound has its own checks. Nord Coloured has a palette.

**Revision 1.2:** SQLite schema alignment, REST completeness, `asyncio.Lock` single-flight, SSE progress, Ollama JSON mode, boundary fixes, all §12.1 gates resolved.

**Revision 1.3 (Full review: correctness, robustness, efficiency, testability).** Defects found in v1.2 and their fixes:

| # | Defect in v1.2 | Fix in v1.3 |
|---|---|---|
| R-01 | **No stage wrote the final prose for T2VA / I2VA / FL2VA / L2VA.** The JSON plan went straight to a "string template" assembler, which cannot produce fluent cinematic prose. | New `prose_writer` stage (§8.1b) turns the JSON plan into shot prose, with a deterministic fallback template. |
| R-02 | **Verbatim dialogue relied on "restore after the fact".** The assembler could not reliably locate a corrupted `<d>` span in LLM output. | **Placeholder protocol** (§8.0): the LLM never sees or copies native script, voice phrases or on-screen text. It writes `{{L1}}`, `{{V:S1}}`, `{{T1}}`; the renderer substitutes. Prompts are stored as `body_template` + rendered `body`; the fixer edits the template only. |
| R-03 | `dialogue_lines.shot_id NOT NULL`, yet T2VA/frame modes have dialogue before any shot exists. No voiceover, cross-cut (`<scenetrans>`) or cutoff (`<cutoff>`) fields, so PF-06/PF-07 could not be satisfied from data. | Schema §6.1: `clip_id`, nullable `shot_id`, `is_voiceover`, `crosses_cut`, `cutoff`, internal `speaker_key` (Sx computed, never user-typed). |
| R-04 | `subject_pictures.picture_ordinal` and `spatial_anchor_shot` were bare integers. Deleting/re-ordering a reference or shot silently corrupted links. | FK `reference_id`, `anchor_shot_id`; ordinals derived; inputs-revision + `stale` prompts (§6.1, PF-30). |
| R-05 | Collision policy keyed on the full filename, so `clip-03-8s.txt` and `clip-03-10s.txt` could coexist (duplicate `NN`). `PLATES.txt` wording was ambiguous. Export had no atomicity. | §10: collision on `NN` regardless of `D`; exclusive-create + temp-rename; precise PLATES contract. |
| R-06 | PF-05/PF-04/PF-10 are text-heuristic yet blocking with no escape, so a false positive would trap the user. | `overridable` rules with logged, explicit user override (§1.5, §9.4). |
| R-07 | Input-only errors (PF-11, PF-13, PF-20) were found only after burning LLM time. | Stage 0 input validation gate before any LLM call (§5.5). |
| R-08 | `ValidationContext`, prompt parser, language/syllable estimators undefined. | §1.5, §5.2 `validation/parser.py`, §9.5 deterministic estimators. |
| R-09 | Sync `sqlite3` inside async handlers; no migration file contract; no multi-tab write protection; `status` could stick at `generating`. | §5.7 runtime hardening. |
| R-10 | SSE specified on a POST (browser `EventSource` is GET-only). Lock covered only `/generate`. | §5.6: streaming via `fetch` + `ReadableStream`; lock covers every LLM-calling endpoint. |
| R-11 | REF2VA `subject_defs` asked an LLM to produce a fixed formula. `plan` variable undefined. Retention markers had no UI. | §8.3 deterministic formula; `plan` defined (§8.0); Step 4 retention table. |
| R-12 | Security of a local server that writes files (DNS-rebinding, path traversal, Browse button impossible in a browser). | §5.7. |
| R-13 | No test plan, no milestones, or explicit handling of unresolved assumptions. | §14 Test plan, §15 Milestones, §16 documented decisions. |

**Revision 1.4 (Self-contained specification).** The complete normative H3 contract is consolidated in §§6–10 and Appendix A. External references, checksum manifests, and unresolved source-file lookups are not part of the implementation contract. Defects found and fixed:

| # | Finding in v1.3 | Fix in v1.4 |
|---|---|---|
| F-01 | Output layout of REF2VA vs the other modes was undefined. | New §7.6 layout contract; PF-01 checks it. |
| F-02 | REF2VA subject formula was wrong. The role slot is a short noun. The outfit noun varies (`uniform`/`outfit`). A person may carry an appositive (`, a convict`). Locations use `including its …, and layout exactly as shown`. A picture anchor line has a free `defining …` clause. | New columns (`outfit_noun`, `appositive`, `feature_list`, `defines_text`); §7.4, §8.3 rewritten. |
| F-03 | Voice was stored per dialogue line, so one speaker could get two voices. Accent clauses were not modelled. | New `speakers` table (voice, accent, pronoun); lines reference it. |
| F-04 | Voiceover wording hard-coded `his lips`. | Pronoun comes from the speaker (PF-06). |
| F-05 | Delivery, accent, shot-size, angle, expression and phrase-bank vocabularies were missing. | Full vocabularies are specified in Appendix A; any resource files are generated from these entries. |
| F-06 | Retention shapes were over-fixed. The picture parenthetical varies by role (`[Shot 1] first frame` / `composition anchor`); the video parenthetical is free text; reasons are about 20 words, not 12. | §8.6 corrected. |
| F-07 | The summary task-type prefix cannot be derived from the references alone (`video editing`, `video continuation`, `audio reuse` depend on user intent). | `clips.task_types_json`, Stage 0 checks, `video editing` summary opening (§8.5). |
| F-08 | Attach order is upload order across all kinds, not grouped by type. The PLATES line format was unspecified. | `references_tokens.position`; §10.2 now defines the exact line format. |
| F-09 | PF-04 required a landing on every move, but the official examples omit it on Static. Modifier vocabulary was unspecified. | Landing required except Static/POV/Shake (warning); four allowed modifier phrases. |
| F-10 | T2VA has no references, yet `<Subject>`/`<Picture>` tokens were not forbidden. | PF-27 extended to T2VA. |
| F-11 | Romanised dialogue (e.g. `wolage hogu`) is not allowed in `<d>`; v1.3 had no handling. | PF-31 and Stage 0 script check. |
| F-12 | The prompt pipeline lacked explicit precision patterns. | Appendix A defines them for `prose_writer`/`shot_writer`; PF-33 warns on violations. |
| F-13 | Music mood-word ban covered only `tense`/`sad`. | PF-08b: `tense`/`sad` error, wider lexicon warning. |
| F-14 | Line-duration formula was ambiguous; Marathi/Bengali have no published rate. | §9.5 explicit formula and "assumed" label. |
| F-15 | Two plausible REF2VA cut phrases were in use. | The app writes `the camera cuts to`; `the shot cuts to` is accepted with a warning and autofixed (PF-02). |
| F-16 | Ref2VA `first_frame`/`keyframe`/`last_frame` links could be mistaken for API frame roles. | §7.6: prompt-level anchors only; the app never emits API roles. |
| F-17 | Style openings, prompt troubleshooting, checklist details, export conventions, and the dialogue-only sentence position were not all defined in one place. | Appendix A and §§7.6, 10.2, and 16 now specify these as product rules; no external file is needed to interpret them. |

**Revision 1.5 (Implementation contract).** v1.4 is the right product, but an implementer could not build it from the text alone. Rules disagreed, the schema could not store the examples, and a few sentences still had empty citations. This revision closes those holes. No external document is required.

| # | Finding in v1.4 | Fix in v1.5 |
|---|---|---|
| C-01 | Three sentences were left unfinished when external citations were removed: the mode hint, the FL2VA reasoning line, and the theme sentence about Markdown. | Each sentence is complete and points only at a section of this document. |
| C-02 | Shot count was both a recommendation and an error. PF-04 omitted the landing word `onto` that Appendix A.5 requires. Named-style prefixes included an editorial ellipsis and a sample shot size (`a medium close-up frames`) that legal shots do not use. Settings still showed the LLM assembler that §8.7 removes. | Appendix A.4 and PF-03 share one minimum/maximum table. The landing list is one list. Style prefixes are exact and stop before the shot size. The assembler control is gone. |
| C-03 | The schema could not store a picture with two roles, a line with two speakers, a cross-cut destination, an audio link that survives renumbering, a gloss, on-screen text placement, a video retention parenthetical, or a shot's silent-versus-action pacing. `voice_source` and retention `reason` were required before anything could fill them. Frame images had no table. | §6.1 and §6.4 store each of those. Empty voice and empty reason are legal until render. Media durations are integer milliseconds. |
| C-04 | `{{V:Sn}}` had to appear "exactly once" and also on every line. The model was still asked to write the speech sentence. Cut-phrase severity, mood-word severity, the line-duration formula, the parser, autofix, JSON schemas, status values, and settings keys were undefined. | §8.0 expands `{{Lk}}` into the whole speech sentence. §5.5, §6.5, §8.1, §9.5, and §9.6 give one algorithm each. |
| C-05 | PF-23 banned visual description widely enough to reject a legal shot. Sound detection was called structural and had no word list. The house sentence could survive into a custom-sound clip. | Subject lines are formula-checked. Shot prose may describe the scene. Sound words, mood words, and the house sentence each have a closed rule. |

**Revision 1.6 (Final certification).** The v1.5 rules stand. This revision records the absolute paths on this machine and sets the health version string to `1.6`.

| # | Finding in v1.5 | Fix in v1.6 |
|---|---|---|
| P-01 | Runtime locations were written as `<repo>/…`. An implementer had no absolute root. | §17.1 sets `<repo>` to `/home/wizdroid/Applications/h3-mechanic`. §17.2 lists every required runtime path. |
| P-02 | The cheatsheets, the workbook, the prompt-writing skill, and the earlier specifications exist on disk and were not named. | §17.3 lists those reference paths. The process does not open them. This specification wins if they disagree. |

**Revision 0.1 (Custom listen port).** v1.6 named `9013` as the process port and mentioned `H3_PORT` only in §17. Settings had no port.

| # | Finding in v1.6 | Fix in v0.1 |
|---|---|---|
| P-03 | The port looked fixed. Health, the stack line, and §17.2 all printed `9013`, and Settings could not store another port. | §5.7 resolves the port from `H3_PORT`, then settings `listen_port`, then `9013`. The saved port applies on the next start. Health `bind` reports the port this process bound. |

**Revision 0.2 (Gaps, schema integrity, and bug fixes).** Audit of v0.1 identified SQL syntax errors, schema-to-validator constraint mismatches, contradictory voice phrase rules, missing API routes, and reordering constraint violations.

| # | Finding in v0.1 | Fix in v0.2 |
|---|---|---|
| B-01 | SQL syntax error `'its'. 'their'` in `subjects.pronoun`, plus `'their'` violates `speakers.pronoun` and has no §8.0 lip-closure rules. | Corrected to `CHECK(pronoun IN ('his','her','its'))` matching `speakers` and Appendix A.9. |
| B-02 | `dialogue_lines.language` CHECK constraint contained obsolete languages (Arabic, Chinese, French, etc.) and omitted `Marathi` and `Bengali`, causing DB insert failures for supported languages. | Replaced with exact supported languages `CHECK(language IN ('English','Kannada','Hindi','Tamil','Telugu','Malayalam','Marathi','Bengali'))`. |
| B-03 | Appendix A.7 stated `later appearances may use in the same … voice`, contradicting §8.0, §9.1 PF-06, §13.6 A-40, and §16 D-09 which mandate repeating the full voice phrase on every line. | Removed contradictory clause from Appendix A.7; aligned with §8.0 and PF-06. |
| B-04 | §6.4 stated that reference reordering uses negative temporary ordinals/positions, violating `CHECK(ordinal >= 1)` and `CHECK(position >= 1)`. | Updated §6.4 to specify using a positive offset shift (e.g. `+1000000`) before final 1..n assignment. |
| B-05 | Typo `'composition'` in `subjects.role` CHECK constraint. | Corrected to `'composition'`. |
| B-06 | Missing endpoints in §5.6 HTTP API table: `POST /api/clips/{id}/references/reorder` and `POST /api/clips/{id}/warmup`. | Added both endpoints with parameters and responses to §5.6 table. |
| B-07 | §5.6.1 over-generalized that all HTTP 409 errors use code `busy`, conflicting with variations limit (`validation`), export collisions (`collision`), and export blocked (`export`). | Clarified error code distribution for 409 responses in §5.6.1. |
| B-08 | §6.5 omitted status transition behavior when `POST /override` removes the final blocking violation on a `blocked` clip. | Clarified that `/override` transitions clip status to `preflight` (or `fixed`) when all blocking violations are cleared. |
| B-09 | §4.4.2 line 260 listed bare style words instead of the 6 allowed pair strings defined in §6.1 and Appendix A.10. | Corrected §4.4.2 to list the 6 pair strings. |
| B-10 | Earlier specification file paths in §17.3 noted as archived historical references. | Clarified §17.3 notes regarding historical specification documents and added v0.1. |

**Revision 0.3 (Anti-overengineering refactor, lightweight references, many-to-many picture linking, and preflight safeguards).** Architectural simplification of REF2VA eliminating the multi-step wizard stepper and dimension blocking; full support for 0, 1, or multiple picture links per Subject; and consolidation of preflight safeguards.

| # | Finding in v0.2 | Fix in v0.3 |
|---|---|---|
| S-01 | **Over-engineered 4-step wizard stepper in REF2VA.** Gating steps and locking progression created friction and blocked rapid iteration. | Abolished wizard stepper in §4.4.6 and §7.4. All cards (Reference Tokens, Subjects & Picture Links, Shots & Audio) are visible simultaneously on a single unified canvas. `clips.wizard_step` retained with default 1 for schema backward compatibility. |
| S-02 | **Rigid image dimension checks blocked reference tokens.** Reference tokens are prompt metadata (`<Picture N>`); requiring exact pixel sizes (256–5760 px, 0.4–2.5 ratio) caused false blocking errors. | Image width and height in `references_tokens` are optional metadata. PF-20 dimension/ratio checks made advisory (warnings only); hard limits on count (≤ 9 images, ≤ 3 videos, ≤ 3 audio, ≤ 12 files) and media duration (2–15s) remain strict safeguards. |
| S-03 | **Subject-to-picture linking lacked flexibility.** v0.2 did not cleanly handle subjects with 0 reference pictures (pure descriptive text) or multiple pictures (e.g. face anchor + outfit reference). | Many-to-many Subject-to-Picture mapping in §6.1, §6.4, §8.3, and Appendix A.9: explicit deterministic formulas for 0 pictures (text-only), 1 picture (identity anchor), and multiple pictures (e.g., face identity from `<Picture 1>` and outfit from `<Picture 2>`). |
| S-04 | **Cross-cut continuation prefix corrupted shot cut header.** Prepending continuation before `[Shot N]` or replacing the cut header broke `CUT_TIME_RE` parsing. | For $N > 1$, cross-cut continuation prefix is placed immediately AFTER the cut header: `[Shot N] At MM:SS.mmm, the camera cuts to <scenetrans> The audio continues seamlessly across the cut. `, preserving cut header structure and continuation semantics (§8.0, PF-07). |
| S-05 | **Prose fallback could drop dialogue and on-screen placeholders.** `fallback_prose` in §8.1b lacked an explicit guarantee that all `{{Lk}}` and `{{Tm}}` tokens are preserved. | §8.1b guarantees placement of all `{{Lk}}` and `{{Tm}}` placeholders in the fallback paragraph without omission. |
| S-06 | **Sound normalization in autofix missed multiline REF2VA sections.** Autofix under `dialogue_only`/`silence` only handled inline fields reliably. | §9.6 autofix rule 5 explicitly normalizes both inline fields and multiline REF2VA sound sections to `N/A`, and ensures proper placement of the house audio sentence. |
| S-07 | **Export collision detection had false negatives across padding.** Checking string prefixes failed to match `clip-1-8s.txt` against `clip-01-8s.txt`. | §10.1 mandates collision detection keyed on integer numeric `NN` alone, matching zero-padded and unpadded file variants and returning HTTP 409 `collision`. |
| S-08 | **Camera move modifier ambiguity on Static, POV, and Shake.** PF-04 wording allowed speed/amplitude modifiers to be misinterpreted on non-moving shots. | PF-04 explicitly forbids all speed and amplitude modifiers on Static, POV, and Shake camera moves as blocking errors. |

---


## 1. Overview

### 1.1 Product intent

**H3 Prompt Studio** is a single-machine, tabbed web application that turns brief creative input into technically correct MiniMax H3 video prompts. It provides a simple, direct, form-driven workflow across five H3 modes — **T2VA**, **I2VA**, **FL2VA**, **L2VA**, **REF2VA** — with a local LLM (via Ollama) doing the drafting, a deterministic preflight validator enforcing every hard rule in this specification, and a pipeline-convention export step. In REF2VA, the app provides a flat, unified single-canvas interface without wizard gates, treating reference items as lightweight prompt tokens (`<Picture N>`, `<Audio N>`, `<Video N>`) and supporting flexible 0, 1, or multiple picture links per Subject. Two model choices stay separate: the **H3 video model** (`MiniMax-H3` or `MiniMax-H3-Max`) sets duration and resolution limits, and the **Ollama drafter** writes the prompt text.

The app's core job is preventing common prompt failures: wrong field order, timestamp typos, `adaptive` ratio on T2VA, speaker IDs out of order, faces in wide shots, sound inserted where the house audio rule forbids it, and budget overruns. The LLM elaborates; the app guarantees the envelope. **Design principle: anything that can be computed or copied is never left to the LLM** (instruction lines, timestamps, speaker IDs, voice phrases, native-script dialogue, on-screen text, subject-definition formula, budgets).

### 1.2 One-paragraph summary

A local web app with two top-level tabs — **Generator** (sub-tabbed per mode: T2VA, I2VA, FL2VA, L2VA, REF2VA) and **Settings** — where the user picks a project, an H3 video model, and a style, enters a brief scene seed (or frame tokens, or full reference sets), selects a pre-fetched Ollama drafter, and a staged pipeline of compact meta-prompts produces a complete, six-section or three-field H3 prompt that passes an in-app preflight checklist before being exported as `clip-<NN>-<D>s.txt` (with a `clip-<NN>-PLATES.txt` attach-order file for REF2VA) into a designated export directory.

### 1.3 Target users

This machine's film-production pipeline (Krea2 character sheets → Qwen Image Edit 2.1 first frames → H3 video, queued through ComfyUI via `batch-scenes` / `batch-images`):

- **Pipeline operator / director** — has scene briefs, plates, reference pictures, audio samples.
- **Prompt auditor** — reviews drafts against the preflight checklist before a render is queued.
- **Batch producer** — runs many clips in sequence (clip numbering, attach-order discipline matter).

### 1.4 Normative scope and traceability

The specification is self-contained. Internal cross-references use section numbers in this document; external source labels are not part of the contract. Appendix A is the complete H3 mode, template, vocabulary, and limit data set. Any application JSON or constants that implement it must match this specification, but the application must not read or require external source files to decide prompt validity.

### 1.5 Canonical validation contract

All validation rules are implemented as a registry-driven validator, never as ad hoc checks in the front end or route handlers. Each rule defines:

- unique rule ID (`PF-01`, `PF-21`, …)
- mode applicability set (`T2VA`, `I2VA`, `FL2VA`, `L2VA`, `REF2VA`, or `ALL`)
- severity (`error` | `warning`)
- internal normative basis (section or Appendix A table)
- `fixable_by_llm` (true for prose/timestamp/format errors; false for metadata/budget/dimension/stale-input errors)
- `basis`: `structural` (decided from structured data or exact grammar) or `heuristic` (decided by text pattern matching)
- `overridable` (bool; only `heuristic` rules may be overridable, §9.4)
- deterministic `check(ctx: ValidationContext) -> list[Violation]`
- user-facing message and suggested correction
- `blocking = (severity == "error") and not overridden`

**`ValidationContext`** (immutable) contains: `clip` row, `references`, `subjects` (+ picture links), `shots`, `speakers`, `dialogue_lines`, `onscreen_texts`, `retention_markers`, `settings snapshot`, `body_template`, rendered `body`, **parsed prompt** (`ParsedPrompt`: instruction line, ordered sections, ordered `[Shot N]` blocks with parsed start time, camera-verb span, `<d>` spans, quoted spans), `inputs_revision`, and the loaded resource vocabularies. Parsing is performed once by `validation/parser.py`; rules never re-parse with private regexes.

Normalized violation object:
`{ "rule_id", "section", "severity", "basis", "message", "suggested_text", "blocking", "fixable", "overridable", "overridden" }`

"Preflight passed" is never a UI-only string: all violations are data, and every export decision derives from that data. A new rule is a new registry entry.

---

## 2. Goals and Non-Goals

### 2.1 Goals

| ID | Goal |
|---|---|
| G-01 | Guided generation in all five modes with the exact templates in §7 and the complete style openings and vocabularies in Appendix A. |
| G-02 | Ollama integration with **drafter prefetch** (`GET /api/tags`) and **user drafter selection** in Settings (A-13). The H3 video model is a separate control. |
| G-03 | A hard preflight validator implementing all rules in §9 before any export. |
| G-04 | REF2VA as a staged pipeline: Reference Manager → Clip Editor → Shot Editor → Summary & Prompt → final six-section prompt. |
| G-05 | House pipeline exports: `clip-<NN>-<D>s.txt` and attach-order PLATES files as defined in §10. |
| G-06 | Modular architecture: a new mode or a new preflight rule is a new module registration. |
| G-07 | Nord-themed minimalist UI (Dark default; Coloured and Light selectable). |
| G-08 | All data in SQLite or JSON inside designated data directories. No external databases, no cloud LLM APIs. |
| G-09 | Meta-prompts optimized for local-model speed: minimum tokens, schema-constrained JSON, strict output shapes, per-stage rule injection only, **placeholders instead of copied text**. |
| G-10 | README (setup) + User Guide (novice and advanced) shipped with the app. |
| G-11 | **Bounded, observable generation**: worst-case LLM call count per generate is documented (§5.5), every stage is timed and recorded, nothing hangs the UI. |
| G-12 | **Reproducible requests**: the same inputs, drafter, and seed produce the same Ollama request payload. The app records the seed. It does not claim identical prose across Ollama versions. |

### 2.2 Non-Goals (v1)

| ID | Non-goal |
|---|---|
| N-01 | **No file upload** in v1. References are tokens paired with captions. Real plate files are referenced by filename text only, with user-typed dimensions/durations. |
| N-02 | No call to the MiniMax API. |
| N-03 | No subtitles in H3 prompts; add subtitles during editing. |
| N-04 | No multi-user auth; bind to `127.0.0.1` only. |
| N-05 | No prompt version-control UI beyond keep-last-5 snapshots. |
| N-06 | No automatic ComfyUI queuing; scene-folder mirroring is v2. |

---

## 3. User Roles and Workflow

1. **Brief Writer** — enters seed / frame tokens / references and clip metadata.
2. **Drafter (the LLM)** — executes meta-prompt stages.
3. **QA / Preflight Operator** — deterministic validator plus the human reviewing violations.
4. **Exporter** — writes `clip-<NN>-<D>s.txt` and PLATES, copies to clipboard.

```
Brief Writer ──► Mode tab ──► metadata
      │
      ▼
Stage 0: input validation (PF-11/13/20, required fields)  ──fail──► highlight inputs, NO LLM call
      │pass
      ▼
LLM stages (per-mode pipeline, §8, progress streamed)
      │
      ▼
Deterministic Renderer (placeholders → final text, instruction line, timestamps)
      │
      ▼
Preflight (§9) ──violations?──► all blocking fixable? ──yes──► Fixer (≤ N loops, template-only edits)
      │pass                          │no                               │
      ▼                              ▼                                 ▼
Review panel ◄──────────── Surface blocking errors ◄──────── Re-render + re-validate
      │
      ├──► optional "Safer framing" (≤ 1 variation per draft, §8.9)
      ▼
Export (§10)
```

---

## 4. UX Design

### 4.1 Theme — Nord

- **Default: Nord Dark.** `nord0 #2E3440` background, `nord1 #3B4252` panels, `nord2 #434C5E` inputs, text `nord6 #ECEFF4` (primary) / `nord4 #D8DEE9` (secondary), accents `nord8 #88C0D0` (primary buttons, active tab), `nord9 #81A1C1` (links, hover), `nord7 #8FBCBB` Generator accent.
- **Status semantics (every theme):** `nord14 #A3BE8C` pass, `nord13 #EBCB8B` warning, `nord11 #BF616A` error, `nord15 #B48EAD` REF2VA accents. Status is never conveyed by colour alone (icon + text label too).
- **Nord Coloured:** background `nord1`, panels `nord10 #5E81AC`, inputs `nord0`, primary text `nord6`, secondary `nord4`, borders `nord9`. Primary buttons filled `nord8` with `nord0` text. Links `nord7`. Generator accent `nord14`. No gradients.
- **Nord Light:** background `nord6`, panels `nord5 #E5E9F0`, inputs `nord4`, text `nord0`, secondary `nord3 #4C566A`, borders `nord4`. Accents `nord8`/`nord9`/`nord7`. Primary buttons `nord10` with `nord6` text.
- **Typography:** system sans (Inter fallback) for UI; monospace (JetBrains Mono fallback) for prompt text, tokens, timestamps, code.
- Minimalist: no gradients, no shadows beyond 1px `nord3` borders. The prompt is one plain-text block. The page does not render it as Markdown.
- All colours are CSS custom properties on `:root[data-theme=…]`; themes switch without reload.

### 4.2 Global layout

```
┌────────────────────────────────────────────────────────────────────┐
│  ◈ H3 Prompt Studio   [Generator] [Settings]   project ▾ · theme · drafter ▾ │
├────────────────────────────────────────────────────────────────────┤
│  [T2VA] [I2VA] [FL2VA (flf2va)] [L2VA (lf2va)] [REF2VA]             │
│  Clip bar: Model ▾ | Style ▾ | Duration ▾ | Resolution ▾ | Ratio ▾ | Language ▾ | Name │
│  ┌─ Inputs ──────────────┐ ┌─ Prompt ─────────────┐ ┌─ Preflight ─┐ │
│  │ (mode-specific)       │ │ (draft / variation)  │ │ pass/fail   │ │
│  │ [Generate ▸] [Manual] │ │ [Copy] [Export ▾]    │ │ violations  │ │
│  └───────────────────────┘ └──────────────────────┘ └─────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

- Header **project** menu selects/creates the project owning the clip.
- Three columns. Below a viewport width of 900px they stack in this order: Inputs, Prompt, Preflight.
- Character and word counters under the prompt. The count is the number of Unicode code points in `body` (§10.1). 7000 or fewer is green; 7001 or more is red.
- "Generate" is disabled while Stage 0 input validation fails or another generation is in flight. The panel shows *which* field blocks it.
- **Stale banner:** when any input changes after a prompt was generated, the prompt shows "Inputs changed since this draft" (PF-30) and export is disabled until regenerate/re-validate.
- **Autosave:** inputs are debounced-saved (500 ms) with `If-Match` revision (§5.7); a "Saved / Saving… / Conflict" indicator is always visible.
- Generation shows a stage progress strip (`seed → prose → render → preflight → fix`) with elapsed time per stage and a **Cancel** button.

### 4.3 Tab architecture

- **Top level:** `Generator` · `Settings`.
- **Generator sub-tabs:** `T2VA` · `I2VA` · `FL2VA (flf2va)` · `L2VA (lf2va)` · `REF2VA`, rendered from `GET /api/modes`.

### 4.4 Layout per tab

#### 4.4.1 Generator shell (shared)

Shared **clip metadata bar**: `clip name` (suggests `clip-<NN>`), `H3 video model`, `style` (`plain`, `80s-bollywood`, `cinematic-modern`, `modern-series`, `noir-thriller`), `plain style pair` (visible when `style == 'plain'`, default `Live-action, cinematic`, validated against `styles.json`), `duration`, `resolution`, `ratio` (mode-dependent), `language`, plus read-only derived fields: prompt char count, shot count estimate, voice-ID assignments.

| H3 video model | Duration | Resolution |
|---|---|---|
| `MiniMax-H3` | integer 4–15 s | `768P`, `2K` |
| `MiniMax-H3-Max` | integer 5–15 s | `480P`, `768P` |

Changing the video model clamps duration into range and clears a resolution the model cannot use (`2K` on H3-Max, `480P` on H3); the UI states what was changed.

#### 4.4.2 T2VA

```
┌ Inputs ────────────────────────────────────────────┐
│ Seed (free text, ≥ 1 sentence, any language)       │
│ [ ] Draft manually (skip LLM stages; run preflight)│
│ Dialogue lines (optional rows):                    │
│   speaker · language ▾ · voice ▾ · delivery ▾      │
│   text (native script, verbatim) · [ ] voiceover   │
│ Sound ▾ [Dialogue only (house default) | Custom | Silence] │
│ [Generate ▸]                                       │
└───────────────────────────────────────────────────┘
```

- The drafter elaborates the seed into sensory detail, physical movement, dialogue only where the user supplied a line or asked for one, setting, one official camera verb per shot, and subject positions, inside the T2VA template in §7.2. "Draft manually": the user writes the body directly (as a template with optional placeholders) and the renderer + preflight run without Ollama.
- Dialogue rows pick a **speaker** from a per-clip speaker list (display name, persona, voice, accent, pronoun — stored once per speaker so voice and wording cannot drift between lines); the app computes `S1`, `S2`… by order of first vocal event (§9.5). Optional voice (`F1`–`F10`, `M1`–`M11`, `K1`–`K2`, or short prose). Empty voices are filled by the drafter from the library by suitability (Appendix A). Library IDs are expanded to paste phrases by the renderer.
- Output template: `integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music`, **no instruction line**, **concrete ratio required** (`21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, never `adaptive`).
- `plain` style opens `[Shot 1]` with one allowed pair from (`Live-action, cinematic`, `2D-animated, cinematic`, `3D CG, cinematic`, `claymation, cinematic`, `watercolor, cinematic`, `vintage film, cinematic`); named styles use the exact opening in Appendix A (§7.1).
- House audio rule default: both sound fields `N/A`, no in-shot sound, and the style opening contains exactly one copy of `The audio contains only the spoken dialogue, with no background music, no ambience, and no sound effects.` Dialogue rows have an optional English gloss. On-screen text is an optional row (verbatim text, straight double quotes in the render). Manual draft is available in every mode: Generate then runs the renderer and preflight only.
- Custom sound: soundscape textarea (1–4 sentences) and music textarea (1–3 sentences or `N/A`) with live sentence counters; Silence: both `N/A`.

#### 4.4.3 I2VA

```
┌ Inputs ────────────────────────────────────────────┐
│ Frame token: <Picture 1> (caption)                 │
│ Source file: [frame_01.png]  W [1536] × H [1024] px│
│ Action input: "she stares at her hands, then       │
│ mumbles a line in Kannada"                         │
│ Dialogue lines / Sound ▾  (as T2VA)                │
│ [Generate ▸]                                       │
│ ── auto-generated instruction line (read-only) ──  │
│ For the target video, at 0.00 seconds into the     │
│ target video, <Picture 1> (from [Shot 1]) is fully │
│ referenced.                                        │
└───────────────────────────────────────────────────┘
```

- The instruction line is **app-generated** from `resources/instruction_lines.json` (exact strings, golden-tested, §14), never typed or LLM-written.
- LLM path: first-frame anchor → action onset → continuous development → result/reaction; restate style + what `<Picture 1>` shows; keep identity, colors, key objects, and layout consistent.
- Ratio is always `adaptive`. One image only. Frame images cannot be combined with reference images/videos/audio.

#### 4.4.4 FL2VA (`FL2VA (flf2va)`)

```
│ First frame: <Picture 1> (caption + W×H px)        │
│ Last frame:  <Picture 2> (caption + W×H px)        │
│ Transition input: "the officer unlocks and swings  │
│ the cell door open"                                │
│ ── auto-generated instruction line (read-only) ──  │
│ How the reference pictures align with the target   │
│ video — Picture 1 (from Shot 1) aligns with the    │
│ 0.00-second mark of the target video; Picture 2    │
│ (from Shot N) aligns with the S.SS-second mark of  │
│ the target video.                                  │
```

- Use the exact FL2VA instruction line in Appendix A; **no angle or square brackets**; `N` = actual final shot index; `S.SS` = `str(duration_s) + ".00"`. The app computes both. Because `N` depends on the generated shot count, the instruction line is rendered **after** the plan is known and is part of the render step, not a pre-LLM constant. (The read-only preview before generation shows `N = 1` and is labelled "preview".)
- The Shots control defaults to 1 (`requested_shot_count`). The final `[Shot N]` must land on Picture 2. Describe motion **between** frames. A single-shot FL2VA is valid at every duration; PF-03's minimum does not apply to it; the maximum still applies if more than one shot.

#### 4.4.5 L2VA (`L2VA (lf2va)`)

```
│ Last frame: <Picture 1> (caption + W×H px)         │
│ Action input: "she crosses the cell and settles    │
│ beneath the window in the morning light"           │
│ ── instruction line (read-only) ──                 │
│ How the reference pictures align with the target   │
│ video — <Picture 1> (from [Shot N]) aligns with    │
│ the S.SS-second mark of the target video.          │
```

- Use the exact L2VA instruction line in Appendix A (angle and square brackets kept). `N` is computed after planning, as in FL2VA.
- Path: plausible preceding state → explicit action/transition → gradual convergence in the final shot → lands on `<Picture 1>`.

#### 4.4.6 REF2VA — flat single-canvas interface

REF2VA provides a flat, unified single-canvas layout displaying all essential cards simultaneously with zero gating or step locks:
1. **Reference Tokens** (`<Picture N>`, `<Audio N>`, `<Video N>`)
2. **Subjects & Picture Mapping** (Subject definition cards with multi-select picture chips)
3. **Shot Editor & Dialogue** (Shots with start times, moves, dialogue lines with speaker and audio links)
4. **Action Bar & Retention** (Preflight checklist preview, Generate button, Retention analysis table, and Export)

Active step in the database schema (`clips.wizard_step`) remains 1 for backward compatibility, but the UI operates without step gating or wizard locks.

```
┌ REF2VA Single-Canvas Layout ──────────────────────────────────────────┐
│ Reference Tokens card                                                 │
│   type ▾   label (auto)   caption        file name      duration/dim  │
│   image    <Picture 1>    "officer plate" officer.png   (optional)    │
│   image    <Picture 2>    "duty uniform"  uniform.png   (optional)    │
│   audio    <Audio 1>      "S1 timbre"     voice_m5.wav  6.0 s         │
│   video    <Video 1>      "pacing ref"    ref_04.mp4    8.0 s         │
│   Budgets: images 2/9 · videos 1/3 · audio 1/3 · files 4/12           │
│ ───────────────────────────────────────────────────────────────────── │
│ Subjects & Picture Mapping card                                       │
│   [+ Add Subject]                                                     │
│   <Subject 1> [person ▾]  role: [officer]  pronoun: [his ▾]           │
│   outfit: [uniform]  appositive: [a prison guard]                     │
│   Linked Pictures: [x <Picture 1> (identity_anchor)]                  │
│                    [x <Picture 2> (outfit)]                           │
│   [+ Link Picture] ▾                                                  │
│   (Supports 0 pictures: text-only description;                        │
│    1 picture: identity anchor;                                        │
│    Multiple pictures: e.g. face anchor + outfit reference)            │
│ ───────────────────────────────────────────────────────────────────── │
│ Shot Editor & Dialogue card                                           │
│   [+ Add Shot]                                                        │
│   [Shot 1] (0.00s) size/angle/move, events, dialogue lines            │
│   [Shot 2] (03.50s) size/angle/move, events, dialogue lines           │
│ ───────────────────────────────────────────────────────────────────── │
│ Action Bar & Retention Analysis card                                  │
│   [Generate Prompt ▸]   [Run Preflight]   [Export Clip]               │
│   Retention table (auto-populated with editable markers/reasons)      │
│   Prompt preview & Preflight checklist results                        │
└───────────────────────────────────────────────────────────────────────┘
```

- **Reference Tokens:** Reference tokens are lightweight prompt metadata tokens (`<Picture N>`, `<Audio N>`, `<Video N>`). Labels auto-assign independently per type in row order; row order is the global upload/attach order across all types (drag to reorder). Reordering/deleting re-derives per-type ordinals and shows a diff ("`<Picture 3>` becomes `<Picture 2>`"); existing prompts become stale (PF-30). Hard budgets are strictly enforced: ≤ 9 images, ≤ 3 videos, ≤ 3 audio, ≤ 12 files total; each audio/video clip is 2–15 s, total ≤ 15 s per type. File dimensions (`width_px`, `height_px`) are optional metadata; if entered, values outside 256–5760 px or ratio outside [0.4, 2.5] generate non-blocking advisory warnings (PF-20), never preventing prompt generation or export.
- **Subjects & Picture Mapping:** Subjects have a role, grammatical pronoun (`his`/`her`/`its`), short role noun such as "officer" (never a picture description), outfit noun (`outfit`/`uniform`), optional appositive (`a convict`), and location/prop feature list. Picture linking is many-to-many: a subject may link 0 pictures (pure text description), 1 picture (identity anchor), or multiple pictures (e.g. `<Picture 1>` for face/identity and `<Picture 2>` for outfit). Each picture link specifies a role: `identity_anchor`, `outfit`, `prop`, `location`, `composition_anchor`, `framing_reference`, `first_frame`, `keyframe`, or `last_frame`. Composition, framing, and frame roles require a shot anchor (`anchor_shot_id`).
- **Shot Editor:** Per shot, select size, angle, camera move, and pacing (`silent` or `action`) from Appendix A; enter the start time (`MM:SS.mmm`; Shot 1 is fixed at 0 ms and untimed in the output) and the events. Dialogue lines pick one or two speakers, a library voice or an audio **row** (`audio_reference_id`, not a typed `<Audio N>` string), an accent clause, a delivery id from Appendix A.8, the native-script text, an optional English gloss, and the voiceover, cross-cut, and cutoff flags. A cross-cut line also picks the destination shot. The app writes `end_ms`. Shot length is checked live against PF-03.
- **Action Bar & Retention:** Stages `subject_defs` (deterministic) → `shot_writer` → `summary_writer` → `retention_writer` → render → preflight. The retention table is editable: the user may pick a marker for each label; otherwise the marker defaults as defined in §8.6 and Appendix A. The LLM writes only each reason. Output is the six sections in exact order.

#### 4.4.7 Settings tab

```
│ Ollama drafter (writes prompt text; does not set H3 limits)      │
│   Endpoint [http://localhost:11434] [Test]                        │
│   Drafter [qwen2.5:7b-instruct ▾] [Refresh models]                │
│   Drafter info: family · params · quantization · context length   │
│   Generation: temperature [0.2] · num_ctx [8192] · timeout [120s] │
│   keep_alive [10m] · seed [auto/fixed]                            │
│   Max fixer retries [2] · seed mode auto / fixed                  │
│ H3 video model  (•) MiniMax-H3  ( ) MiniMax-H3-Max                │
│ Defaults: Duration · Resolution · Ratio · Style · Language · Audio│
│   Export directory [text path, validated]  [Validate]             │
│   Collision policy [Auto-increment NN ▾]                          │
│   Listen port [9013]  (saved port applies on the next start)      │
│ Voice library (read-only)  F1–F10 · M1–M11 · K1–K2  [search]      │
│ Theme  Nord Dark / Nord Coloured / Nord Light                     │
│ Data: SQLite path · exports · backups · specification version     │
```

- The drafter dropdown is **prefetched** on startup and refresh via `GET /api/tags`; free-text names are disallowed. Drafter info from `POST /api/show` (family, parameter size, quantization, **context length**). If `num_ctx` exceeds the model's trained context length the UI warns. Unreachable Ollama or empty list shows an explicit error with `ollama pull <model>` hint — never a silent blank.
- Export directory is a **text field validated server-side** (exists or creatable, writable, resolves under an absolute path, not a symlink escape). A browser cannot open a native folder picker that returns a server path, so there is no "Browse" button.
- Listen port is the integer field `listen_port`. The rules are in §5.7. The screen shows the port this process bound and the saved port. When they differ, it says the saved port is used on the next start.
- Voice library is the read-only vocabulary defined in Appendix A; searchable; paste phrases copyable.
- Settings resolution order for a clip: **clip value → project `default_settings` → global settings → built-in default**.

---

## 5. Architecture

### 5.1 Stack

- **Back-end:** Python 3.10+, FastAPI, Uvicorn, `httpx.AsyncClient`, and `jsonschema`. SQLite is the standard-library `sqlite3`. Runtime dependencies are those four packages, pinned to exact versions in `requirements.txt` when the app is implemented. The process binds `127.0.0.1` and the listen port from §5.7. The default port is `9013`.
- **Front-end:** static SPA (vanilla JS ES modules, no build step) served by the same process; tab/mode metadata fetched from the registry.
- **Storage:** one SQLite DB; bundled read-only JSON vocabularies validated at startup and in tests against the normative tables in this specification.
- **Data directories:** §17.2. The root is `/home/wizdroid/Applications/h3-mechanic/data/` — `h3studio.db`, `exports/`, `backups/`, `logs/`.

### 5.2 Module layout and boundaries

```
h3-prompt-studio/          # application name, not a directory; files live under §17.1
├── app/
│   ├── main.py                 # app factory; routes; lifespan startup checks (§5.7)
│   ├── core/
│   │   ├── config.py           # paths, defaults, env overrides
│   │   ├── locks.py            # single-flight generation coordinator + cancellation
│   │   ├── security.py         # Host/Origin allow-list, path validation
│   │   └── registry.py         # ModeRegistry, RuleRegistry, StageRegistry, ExportWriterRegistry
│   ├── llm/
│   │   ├── connector.py        # Ollama client: list_models(), model_info(), generate()
│   │   └── prompt_bank.py      # meta-prompts + stage JSON schemas (§8)
│   ├── storage/
│   │   ├── db.py               # connection factory, PRAGMAs, migration runner
│   │   ├── invariants.py       # mode, budget, and label predicates outside SQL CHECKs
│   │   ├── migrations/         # 0001_init.sql, 0002_….sql (forward-only, transactional)
│   │   └── repositories.py     # one repository per aggregate
│   ├── engine/
│   │   ├── base.py             # ModeEngine ABC, PipelineStage ABC
│   │   ├── pipelines.py        # per-mode stage sequences + progress emitter
│   │   ├── placeholders.py     # §8.0 placeholder protocol: tokenise / render / verify
│   │   ├── renderer.py         # deterministic assembler: template → final prompt
│   │   ├── modes/  t2va.py i2va.py fl2va.py l2va.py ref2va.py
│   │   └── stages/ seed_elaboration, frame_action, prose_writer, subject_defs,
│   │               shot_writer, summary_writer, retention_writer,
│   │               preflight_fixer, safer_framing
│   ├── validation/
│   │   ├── parser.py           # ParsedPrompt: sections, shots, cut times, <d> spans, quotes
│   │   ├── estimators.py       # word/syllable/line-duration estimators (§9.5)
│   │   ├── preflight.py        # runner → normalized violations
│   │   └── rules/              # one file per rule family (PF-xx)
│   ├── export/exporter.py      # naming, collision, atomic writes, PLATES, backups
│   ├── resources/               # derived read-only data; normative values are in Appendix A
│   │   ├── voices.json camera_moves.json task_types.json retention_markers.json
│   │   ├── languages.json shot_budgets.json styles.json instruction_lines.json
│   │   └── accents.json deliveries.json shot_sizes.json angles.json mood_words.json
│   └── web/                    # index.html, css/nord.css, js/*
├── data/                       # runtime-created
├── docs/ README.md USER_GUIDE.md specifications/
└── tests/                      # pytest (§14)
```

### 5.3 Module boundaries and responsibilities

| Module | Owns | Never does |
|---|---|---|
| `llm/connector.py` | Ollama HTTP, `format`/`options`, timeouts, `done_reason` detection | Know H3 rules |
| `llm/prompt_bank.py` | Meta-prompt texts, stage JSON schemas | Call the model |
| `engine/modes/*` | Mode template, required inputs | Run preflight |
| `engine/stages/*` | One LLM round-trip each; parse + schema-validate | Hold cross-stage state |
| `engine/placeholders.py` + `renderer.py` | Tokenise inputs, render final text, verify placeholder integrity | Call the LLM |
| `engine/pipelines.py` | Stage order per mode; progress events | Rule logic |
| `validation/*` | Parsing, estimators, rules, violations | Edit prompts |
| `export/exporter.py` | File naming/atomic write/PLATES/backups | Change prompt text |
| `storage/` | Persistence, migrations, FK enforcement | UI, LLM, rules |

### 5.4 Extension points

1. **New mode** = subclass `ModeEngine` + `register_mode(id, engine, tab_meta)`; the tab appears via `GET /api/modes`.
2. **New preflight rule** = `@rule(id="PF-31", mode=[…], severity="error", fixable=True, basis="structural", overridable=False, normative_basis="§9 / Appendix A")`.
3. **New LLM stage** = registration in `prompt_bank.py` + a slot in the pipeline list.
4. **New export writer** = `ExportWriterRegistry` entry.
5. **New vocabulary** = add a normative entry to this specification, then mirror it in the application resource file and schema tests.

### 5.5 Generation, Ollama call contract, and repair

**Stage 0 — input validation (before any LLM call).** Failure returns field-level violations and makes **zero** Ollama calls. The checks are:

- PF-11, PF-13, and PF-20. Duration totals add stored `duration_ms` values. Each audio or video row is 2000–15000 ms and each type sums to at most 15000 ms. A null duration or dimension on a row that the mode requires is a failure.
- `style_id`, `plain_style_pair`, line language, delivery id, and accent are members of the closed lists in Appendix A.
- T2VA requires a non-empty `seed_text`, or a non-empty manual template.
- I2VA and L2VA require exactly one image and a non-empty `action_text`, unless the clip is a manual draft. FL2VA requires exactly two images, first frame then last frame, and a non-empty `action_text`, unless manual.
- REF2VA requires at least one reference; a comma-free `role_phrase` of 1–40 characters on every subject; a non-empty `feature_list` on every location; a non-empty comma-free `outfit_noun` on every person; an `anchor_shot_id` on every composition, framing, or frame role; at least one shot whose first start is 0 ms; at least one task type; a video row when `video editing` or `video continuation` is selected; an audio row when `audio reuse` is selected.
- Captions, filenames, personas, role phrases, and on-screen texts contain no newline. Filenames contain no `/` or `\`.
- Every line passes PF-31. `crosses_cut = 1` requires a `dest_shot_id` different from `shot_id`. Manual draft requires a persona and either a voice source or an audio reference.
- User-authored REF2VA shots satisfy the PF-03 minima. A non-null `requested_shot_count` is inside the Appendix A.4 maximum, and inside the minimum unless the one-shot FL2VA waiver applies.

**Ollama request contract.** The app calls `{endpoint}/api/generate` with `stream: false`. `{endpoint}` defaults to `http://127.0.0.1:11434`. That URL is the Ollama server, not this app. This app's generate route is `POST /api/clips/{id}/generate`.

- `model`: the selected drafter. `keep_alive`: setting (default `10m`).
- `options`: `temperature`, `num_ctx`, `seed`, `num_predict`. `seed` is `seed_value` when `seed_mode` is `fixed`, otherwise a random integer in `0 .. 4294967295`. The value actually sent is stored on the prompt. `num_predict` is `ceil(word_cap × 2.2)` using this table.

| Stage | Word cap |
|---|---:|
| `seed_elaboration` | 320 |
| `frame_action_elaboration` | 260 |
| `prose_writer` | the §8.1b target for the duration, × 1.4 |
| `shot_writer` | 560 |
| `summary_writer` | 90 |
| `retention_writer` | 25 × the number of empty reasons |
| `preflight_fixer` | words in the template + 200 |
| `safer_framing` | words in the template + 80 |
- JSON stages (`seed_elaboration`, `frame_action_elaboration`): `format` = the stage's **JSON Schema** (structured outputs). If the Ollama server rejects a schema object, fall back to `format: "json"`. Output is always validated again with the schema in Python (`jsonschema`/pydantic) — constrained decoding is a helper, not a guarantee.
- Pre-flight token budget: estimated prompt tokens (chars/3.2, conservative) + `num_predict` must be ≤ 0.9 × `num_ctx`; otherwise the stage fails fast with an actionable message (raise `num_ctx` or shorten input) instead of silently truncating at the front of the context.
- Timeouts: connect 5 s; read = Settings `timeout` (default 120 s). First call after idle may include model load; the app issues a cheap warm-up (`num_predict: 1`) when the user opens a clip tab or presses Generate.
- Cancellation: the Cancel button aborts the in-flight httpx request and releases the lock.

**Failure states handled explicitly:** JSON parse/schema failure; empty output; truncated (`done_reason == "length"`); semantic mismatch; overlong output (> stage limit or > 7000 Unicode code points after render); placeholder integrity failure (§8.0); mixed-language violation.

**Stage retry:** on a structural failure (parse/schema/empty/truncated/placeholder-integrity) the stage runner retries **once** with temperature raised by 0.1 and seed set to `(seed + 1) mod 4294967296`, then aborts the pipeline with a stage error (partial results kept, user may edit and resume).

**Preflight / fix loop** after rendering:
1. Persist violations to `prompts.preflight_json`.
2. If any **blocking, non-overridable** violation is `fixable == false` ⇒ no LLM fixer; block export; highlight offending inputs.
3. If all blocking violations are `fixable == true` ⇒ run `preflight_fixer` on `body_template` with only the violation list.
4. **Integrity guard:** the fixer's output must contain exactly the same multiset of placeholders as its input (§8.0) and keep every unflagged shot header/timestamp; otherwise the output is discarded and counted as a retry (the template is never replaced by an unverified rewrite).
5. Re-render, re-run the **full** validator. Stop after N retries (Settings default 2); remaining errors block export.

**Worst-case LLM calls per Generate** (documented and tested): T2VA/frame modes = (plan 1 + retry 1) + (prose 1 + retry 1) + fixer N(2) = **≤ 6**; REF2VA = (shot_writer 1+1) + (summary 1+1) + (retention reasons 1+1) + fixer 2 = **≤ 8** (`subject_defs` is deterministic). A final "Safer framing" is a separate user action (+1 call). The retention call is skipped when every reason is already non-empty. The prose fallback is not an extra call. A warm-up (`num_predict` 1) and `POST /api/clips/{id}/subjects/{sid}/suggest-role` (exactly one call, no retry) sit outside this budget. Warm-up takes the same lock, is skipped when the lock is held, and its failure does not fail a later generate. Suggest-role failure returns `422` and leaves the subject unchanged.

**Concurrency:** all LLM-calling endpoints (`/generate`, `/fix`, `/variations`) acquire one process-wide lock. A second request gets `409 Conflict` with the active clip id. The lock is released on completion, error, cancel, or client disconnect (try/finally). On startup, any clip with `status == 'generating'` is reset to `draft` (crash recovery).

### 5.6 HTTP API (v1)

Streaming: `POST /api/clips/{id}/generate` with header `Accept: application/x-ndjson` streams one JSON object per line (`{"event":"stage_start|stage_done|stage_retry|violations|done|error","stage":…,"ms":…}`); without it, returns the final JSON. The front end consumes it with `fetch` + `ReadableStream` (not `EventSource`, which cannot POST). Every mutating route requires `If-Match: <revision>` where a revision exists (§5.7); mismatch ⇒ `412 Precondition Failed`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | §5.6.1 health object |
| GET | `/api/models` | prefetch `GET /api/tags` → cached model list |
| GET | `/api/models/{name}` | `POST /api/show` → family/params/quantization/context length |
| GET | `/api/modes` | registry: id, label, alias, inputs schema, ratio policy |
| GET | `/api/voices` | voice library |
| GET/PUT | `/api/settings` | global settings |
| GET/POST | `/api/projects` | list/create |
| PUT/DELETE | `/api/projects/{id}` | update/delete project |
| GET/POST | `/api/projects/{id}/clips` | list/create clips |
| GET/PUT/DELETE | `/api/clips/{id}` | clip metadata and inputs |
| POST | `/api/clips/{id}/duplicate` | copy references, subjects, pictures, shots, speakers, lines, on-screen text, and retention. Do not copy prompts. New clip, status `draft`, revision 1 |
| GET/POST | `/api/clips/{id}/references` | list/create reference tokens |
| PUT/DELETE | `/api/clips/{id}/references/{rid}` | update/delete (re-derives ordinals; marks prompts stale) |
| POST | `/api/clips/{id}/references/reorder` | reorder reference tokens by position; re-derives ordinals and marks prompts stale |
| GET/POST | `/api/clips/{id}/subjects` | list/create subjects |
| PUT/DELETE | `/api/clips/{id}/subjects/{sid}` | update/delete |
| POST | `/api/clips/{id}/subjects/{sid}/pictures` | link a picture (`reference_id`, role, `anchor_shot_id`) |
| PUT/DELETE | `/api/clips/{id}/subjects/{sid}/pictures/{pid}` | update/remove link |
| GET/POST | `/api/clips/{id}/shots` | list/create shots (recomputes `end_ms`) |
| PUT/DELETE | `/api/clips/{id}/shots/{shotId}` | update/delete |
| GET/POST | `/api/clips/{id}/speakers` | list/create speakers |
| PUT/DELETE | `/api/clips/{id}/speakers/{speakerId}` | update/delete a speaker |
| GET/POST | `/api/clips/{id}/onscreen` | list/create on-screen texts |
| PUT/DELETE | `/api/clips/{id}/onscreen/{tid}` | update/delete an on-screen text |
| POST | `/api/clips/{id}/subjects/{sid}/suggest-role` | one Ollama call; returns `{role_phrase}` of at most 4 words; the user must save it |
| GET/POST | `/api/clips/{id}/lines` | clip-level dialogue lines (T2VA/frame modes; also lists all REF2VA lines) |
| GET/POST | `/api/shots/{shotId}/lines` | shot-level lines (REF2VA) |
| PUT/DELETE | `/api/lines/{lineId}` | update/delete a line (either scope) |
| GET/PUT | `/api/clips/{id}/retention` | retention markers (REF2VA Step 4) |
| POST | `/api/clips/{id}/validate-inputs` | Stage 0 only; returns field-level violations |
| POST | `/api/clips/{id}/generate` | run mode pipeline (§5.5) |
| POST | `/api/clips/{id}/generate/cancel` | cancel in-flight generation |
| POST | `/api/clips/{id}/warmup` | cheap drafter warm-up call (`num_predict: 1`); non-blocking |
| POST | `/api/clips/{id}/preflight` | validate current prompt |
| POST | `/api/clips/{id}/override` | record an explicit override for an `overridable` violation (§9.4) |
| POST | `/api/clips/{id}/fix` | run fixer loop |
| POST | `/api/clips/{id}/variations` | one safer-framing variation per draft; `409` if one exists |
| POST | `/api/clips/{id}/select` | choose draft or variation as export source |
| POST | `/api/clips/{id}/export` | write files + snapshot; returns `{filename, raw_prompt}` |
| GET | `/api/vocab/{name}` | `camera-moves`, `task-types`, `retention-markers`, `languages`, `styles`, `shot-budgets`, `voices`, `accents`, `deliveries`, `shot-sizes`, `angles`, `mood-words` |

### 5.6.1 Health, errors, and Ollama proxy

`GET /api/models` calls Ollama `GET {endpoint}/api/tags` and caches the result. `GET /api/models/{name}` calls Ollama `POST {endpoint}/api/show`. `{name}` is URL-decoded once. Neither route is an Ollama path on this app.

`GET /api/health` returns:

```json
{"status":"ok","specification_version":"0.3","schema_version":1,"ollama":"reachable","model_count":0,"bind":"127.0.0.1:9013"}
```

`ollama` is `reachable` or `unreachable`. `specification_version` is the string `0.3`. `schema_version` is the applied migration integer. `bind` is `127.0.0.1:` plus the port this process bound (§5.7). The sample above uses the default port.

Every error body is:

```json
{"error":{"code":"stage_0","message":"...","violations":[],"active_clip_id":null,"current_revision":null}}
```

`code` is one of `stage_0`, `validation`, `busy`, `precondition`, `not_found`, `ollama`, `export`, `collision`. `409` uses `busy` and sets `active_clip_id` when the process generation lock is held; for export file collisions or duplicate variation requests, `409` returns `collision`, `export`, or `validation` with `active_clip_id: null`. `412` uses `precondition` and sets `current_revision`. Request and response fields use the §6.1 column names. Unknown fields are `422` / `validation`.

Every mutating clip route, including speakers, on-screen text, suggest-role, generate, fix, variations, select, override, and export, requires `If-Match` of that clip's `revision`.

### 5.7 Runtime hardening

- **Bind and origin:** bind `127.0.0.1` only. The listen port is a base-10 integer from 1 to 65535. The default is 9013. Startup resolves it in this order: (1) `H3_PORT`, when the variable is set, after stripping leading and trailing whitespace; (2) the stored settings value `listen_port`, when that row exists; (3) 9013. An empty `H3_PORT`, or any resolved value that is not an integer in that range, aborts startup with a clear message. The process does not fall back to another port. If the `listen_port` row is missing, startup inserts `9013` before it binds. A `PUT /api/settings` value outside 1–65535 is `422` / `validation` and leaves the stored value unchanged. Saving a new port does not rebind the running process. If the bind call fails, startup aborts with the operating-system message and does not try another port. `H3_HOST`, if set, must be `127.0.0.1`; any other value aborts startup. Reject requests whose `Host` is not `localhost`/`127.0.0.1`/`[::1]:<port>` and, on mutating routes, whose `Origin` (if present) is not the same origin (DNS-rebinding and drive-by-POST defence for an app that writes files).
- **Paths:** export directory is resolved with `Path.resolve()`; filenames are generated by the app only (never from user text); `clip.name` is sanitized to `[A-Za-z0-9._-]` for display use only.
- **SQLite:** every connection runs `PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;`. Route handlers that touch SQLite are plain `def` (run in FastAPI's threadpool) or use `run_in_threadpool`; one connection per request/thread; no connection shared across threads. Multi-row writes use a single transaction.
- **Migrations:** forward-only `storage/migrations/NNNN_*.sql`, each in a transaction, recorded in `schema_version`. A copy of the DB is saved to `data/backups/h3studio-pre-migration-<ts>.db` before applying any migration. Opening a DB with a newer `schema_version` than the app knows aborts startup with a clear message.
- **Optimistic concurrency:** `clips.revision` (integer, +1 on every clip or child write). Clients send `If-Match`; mismatch ⇒ `412` and the UI offers "reload". Prevents two browser tabs overwriting each other.
- **Inputs revision:** `clips.inputs_revision` increments only for the generation-relevant columns and child tables listed in §6.4. Each prompt stores the `inputs_revision` it was built from; mismatch ⇒ stale (PF-30).
- **Specification integrity:** application resource files are derived from §§6–10 and Appendix A. Tests compare resource values to specification fixtures or constants maintained with the application; startup does not load or verify external documents, source trees, or checksum manifests.
- **Logging:** structured logs to `data/logs/app.log` (rotating); LLM prompts/responses are logged at DEBUG only, never to the UI.
- **Time:** all timestamps ISO-8601 UTC; clip numbering is not time-based.

---

## 6. Data Models

### 6.1 SQLite schema (`data/h3studio.db`)

All tables carry `created_at`, `updated_at` (ISO-8601 UTC text). Repositories set `updated_at`; schema is versioned via `schema_version`.

### 6.1.1 Serialization contract

All stage payloads persist relationally and are snapshotted into `prompts.structured_payload_json`. Shapes:

- `subject_definition`: `subject_id`, `ordinal`, `label`, `role`, `role_phrase`, `pronoun`, `picture_refs` (list of `{ reference_id, picture_ordinal, reference_role, anchor_shot_ordinal }`), `raw_text`
- `shot`: `shot_id`, `ordinal`, `start_ms`, `end_ms`, `size`, `angle`, `camera_move`, `pacing`, `events`, `dialogue_line_ids`, `reference_anchors`
- `dialogue_line`: `line_id`, `line_order`, `speaker_id`, `speaker_id_2`, `dest_shot_id`, `gloss`, `speaker_label` (computed `S1` or `S1,S2`), `language`, `text_raw`, `text_in_prompt`, `delivery`, `is_voiceover`, `crosses_cut`, `cutoff`. The speaker object includes `display_name`, `voice_source`, `audio_reference_id`, `accent`, `pronoun`, `persona`, `subject_id`
- `reference_token`: `kind`, `ordinal`, `label`, `caption`, `source_file`, `duration_ms`, `width_px`, `height_px`, `role_hint`, `position`
- `retention_marker`: `area`, `subject_id` or `reference_id`, `parenthetical`, `shot_ordinals_json`, `marker`, `reason`, `marker_source` (`user`|`default`). The label is computed at render

Raw prompt text and parsed structured data are persisted separately. The stored structured data, not the preview, is canonical.

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  notes TEXT DEFAULT '',
  default_settings TEXT,
  revision INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

CREATE TABLE clips (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('T2VA','I2VA','FL2VA','L2VA','REF2VA')),
  name TEXT NOT NULL DEFAULT 'Clip',
  h3_model TEXT NOT NULL DEFAULT 'MiniMax-H3' CHECK(h3_model IN ('MiniMax-H3','MiniMax-H3-Max')),
  style_id TEXT NOT NULL DEFAULT 'plain' CHECK(style_id IN ('plain','80s-bollywood','cinematic-modern','modern-series','noir-thriller')),
  plain_style_pair TEXT NOT NULL DEFAULT 'Live-action, cinematic' CHECK(plain_style_pair IN (
    'Live-action, cinematic','2D-animated, cinematic','3D CG, cinematic','claymation, cinematic','watercolor, cinematic','vintage film, cinematic')),
  duration_s INTEGER NOT NULL,
  resolution TEXT NOT NULL,
  ratio TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'English' CHECK(language IN ('English','Kannada','Hindi','Tamil','Telugu','Malayalam','Marathi','Bengali')),
  audio_policy TEXT NOT NULL DEFAULT 'dialogue_only' CHECK(audio_policy IN ('dialogue_only','custom','silence')),
  seed_text TEXT NOT NULL DEFAULT '',
  action_text TEXT NOT NULL DEFAULT '',
  custom_soundscape TEXT NOT NULL DEFAULT '',
  custom_music TEXT NOT NULL DEFAULT 'N/A',
  task_types_json TEXT NOT NULL DEFAULT '[]',
  task_types_touched INTEGER NOT NULL DEFAULT 0 CHECK(task_types_touched IN (0,1)),
  requested_shot_count INTEGER CHECK(requested_shot_count IS NULL OR requested_shot_count BETWEEN 1 AND 4),
  manual_draft INTEGER NOT NULL DEFAULT 0 CHECK(manual_draft IN (0,1)),
  manual_template TEXT NOT NULL DEFAULT '',
  wizard_step INTEGER NOT NULL DEFAULT 1 CHECK(wizard_step BETWEEN 1 AND 4),
  revision INTEGER NOT NULL DEFAULT 1,
  inputs_revision INTEGER NOT NULL DEFAULT 1,
  selected_prompt_id INTEGER,
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','generating','preflight','blocked','fixed','failed','exported')),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  CHECK (
    (h3_model = 'MiniMax-H3' AND duration_s BETWEEN 4 AND 15 AND resolution IN ('768P','2K'))
    OR (h3_model = 'MiniMax-H3-Max' AND duration_s BETWEEN 5 AND 15 AND resolution IN ('480P','768P'))
  ),
  CHECK (
    (mode = 'T2VA' AND ratio IN ('21:9','16:9','4:3','1:1','3:4','9:16'))
    OR (mode IN ('I2VA','FL2VA','L2VA') AND ratio = 'adaptive')
    OR (mode = 'REF2VA' AND ratio IN ('adaptive','21:9','16:9','4:3','1:1','3:4','9:16'))
  )
);

CREATE TABLE references_tokens (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('image','video','audio')),
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  caption TEXT NOT NULL,
  role_hint TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL CHECK(position >= 1),
  source_file TEXT NOT NULL DEFAULT '',
  duration_ms INTEGER,
  width_px INTEGER,
  height_px INTEGER,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(clip_id, kind, ordinal),
  UNIQUE(clip_id, position),
  CHECK (kind = 'image' OR (width_px IS NULL AND height_px IS NULL)),
  CHECK (kind <> 'image' OR duration_ms IS NULL),
  CHECK (width_px IS NULL OR width_px > 0),
  CHECK (height_px IS NULL OR height_px > 0),
  CHECK (duration_ms IS NULL OR duration_ms BETWEEN 2000 AND 15000)
);

CREATE TABLE subjects (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  role TEXT NOT NULL CHECK(role IN ('person', 'character', 'crowd', 'body_part', 'face', 'hair', 'expression', 'pose', 'animal', 'creature', 'plant', 'robot', 'outfit', 'accessory', 'jewelry', 'footwear', 'headwear', 'makeup', 'tattoo', 'prop', 'weapon', 'vehicle', 'furniture', 'food', 'drink', 'tool', 'device', 'instrument', 'location', 'architecture', 'interior', 'landscape', 'background', 'weather', 'time_of_day', 'season', 'lighting', 'color_palette', 'texture', 'material', 'pattern', 'effect', 'particle', 'camera_angle', 'composition', 'style', 'art_medium', 'text', 'logo', 'symbol', 'other')),
  role_phrase TEXT NOT NULL DEFAULT '',
  pronoun TEXT NOT NULL DEFAULT 'her' CHECK(pronoun IN ('his','her','its')),
  outfit_noun TEXT NOT NULL DEFAULT 'outfit',
  appositive TEXT NOT NULL DEFAULT '',
  feature_list TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  raw_text TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(clip_id, ordinal)
);

CREATE TABLE shots (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
  end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
  size TEXT NOT NULL DEFAULT '',
  angle TEXT NOT NULL DEFAULT '',
  camera_move TEXT NOT NULL DEFAULT '',
  pacing TEXT NOT NULL DEFAULT 'action' CHECK(pacing IN ('silent','action')),
  events TEXT NOT NULL DEFAULT '',
  reference_anchors_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(clip_id, ordinal)
);

CREATE TABLE subject_pictures (
  id INTEGER PRIMARY KEY,
  subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  reference_id INTEGER NOT NULL REFERENCES references_tokens(id) ON DELETE CASCADE,
  reference_role TEXT NOT NULL CHECK(reference_role IN (
    'identity_anchor','outfit','prop','location','composition_anchor',
    'framing_reference','first_frame','keyframe','last_frame')),
  anchor_shot_id INTEGER REFERENCES shots(id) ON DELETE SET NULL,
  defines_text TEXT NOT NULL DEFAULT '',
  UNIQUE(subject_id, reference_id, reference_role)
);

CREATE TABLE speakers (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL,
  subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
  voice_source TEXT NOT NULL DEFAULT '',
  audio_reference_id INTEGER REFERENCES references_tokens(id) ON DELETE SET NULL,
  accent TEXT NOT NULL DEFAULT '',
  pronoun TEXT NOT NULL DEFAULT 'his' CHECK(pronoun IN ('his','her','its')),
  persona TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(clip_id, display_name)
);

CREATE TABLE dialogue_lines (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  shot_id INTEGER REFERENCES shots(id) ON DELETE SET NULL,
  dest_shot_id INTEGER REFERENCES shots(id) ON DELETE SET NULL,
  line_order INTEGER NOT NULL DEFAULT 1,
  speaker_id INTEGER NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
  speaker_id_2 INTEGER REFERENCES speakers(id) ON DELETE SET NULL,
  language TEXT NOT NULL CHECK(language IN ('English','Kannada','Hindi','Tamil','Telugu','Malayalam','Marathi','Bengali')),
  text_raw TEXT NOT NULL,
  text_in_prompt TEXT NOT NULL DEFAULT '',
  gloss TEXT NOT NULL DEFAULT '',
  delivery TEXT NOT NULL DEFAULT 'none' CHECK(delivery IN (
    'none','whisper','shout','command','mumble','sob','choked','plead','sarcastic','tender',
    'menacing','cold','deadpan','excited','breathless','nervous','laughing','furious',
    'interrogation','murmur','singing')),
  is_voiceover INTEGER NOT NULL DEFAULT 0 CHECK(is_voiceover IN (0,1)),
  crosses_cut INTEGER NOT NULL DEFAULT 0 CHECK(crosses_cut IN (0,1)),
  cutoff INTEGER NOT NULL DEFAULT 0 CHECK(cutoff IN (0,1)),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  CHECK(speaker_id_2 IS NULL OR speaker_id_2 <> speaker_id)
);

CREATE TABLE onscreen_texts (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  shot_id INTEGER REFERENCES shots(id) ON DELETE SET NULL,
  text_raw TEXT NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(clip_id, ordinal)
);

CREATE TABLE retention_markers (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  area TEXT NOT NULL CHECK(area IN ('visual','audio')),
  subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
  reference_id INTEGER REFERENCES references_tokens(id) ON DELETE CASCADE,
  parenthetical TEXT NOT NULL DEFAULT '',
  shot_ordinals_json TEXT NOT NULL DEFAULT '[]',
  marker TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  marker_source TEXT NOT NULL DEFAULT 'default' CHECK(marker_source IN ('user','default')),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(clip_id, ordinal),
  CHECK((subject_id IS NULL) <> (reference_id IS NULL))
);

CREATE TABLE prompts (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  generation_id TEXT NOT NULL,
  stage TEXT NOT NULL CHECK(stage IN ('draft','fixed','variation')),
  inputs_revision INTEGER NOT NULL,
  summary_text TEXT NOT NULL DEFAULT '',
  body_template TEXT NOT NULL,
  body TEXT NOT NULL,
  char_count INTEGER NOT NULL CHECK(char_count >= 0),
  structured_payload_json TEXT,
  preflight_json TEXT,
  overrides_json TEXT NOT NULL DEFAULT '[]',
  fixer_retries INTEGER NOT NULL DEFAULT 0,
  drafter_model TEXT,
  ollama_seed INTEGER,
  stage_timings_json TEXT,
  prose_fallback INTEGER NOT NULL DEFAULT 0 CHECK(prose_fallback IN (0,1)),
  exported_filename TEXT,
  exported_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE INDEX idx_references_clip ON references_tokens(clip_id, position);
CREATE INDEX idx_shots_clip ON shots(clip_id, ordinal);
CREATE INDEX idx_lines_clip ON dialogue_lines(clip_id, line_order);
CREATE INDEX idx_prompts_clip ON prompts(clip_id, created_at);
CREATE INDEX idx_subject_pictures_subject ON subject_pictures(subject_id);
CREATE INDEX idx_speakers_clip ON speakers(clip_id);
CREATE INDEX idx_onscreen_clip ON onscreen_texts(clip_id);
CREATE INDEX idx_retention_clip ON retention_markers(clip_id);
```

Indexes are the `CREATE INDEX` statements in the script above.


### 6.2 Derived resources and on-disk JSON

The application may serialize Appendix A into the bundled read-only JSON files named in §5.2. Those files are implementation assets. They match this specification, and they carry no external URL, file path, vendor hash, or checksum. `data/backups/clip-<id>-<ts>.json` stores the full clip-state snapshot on every export; retain the last five per clip.

### 6.3 Model invariants

| Invariant | Normative definition |
|---|---|
| `MiniMax-H3`: duration integer 4–15; resolution `768P` or `2K` | §4.4.1, Appendix A.1 |
| `MiniMax-H3-Max`: duration integer 5–15; resolution `480P` or `768P` | §4.4.1, Appendix A.1 |
| T2VA ratio concrete; I2VA/FL2VA/L2VA `adaptive`; REF2VA either | §7.1, Appendix A.1 |
| REF2VA: images ≤ 9, videos ≤ 3, audio ≤ 3, files ≤ 12 | §4.4.6, Appendix A.1 |
| Audio/video clips each 2000–15000 ms, total ≤ 15000 ms per type, stored as `duration_ms` | §6.1, §6.4, Appendix A.1 |
| Images: width and height optional metadata; 256–5760 px and ratio ∈ [0.4, 2.5] are advisory checks | §4.4.6, §9.1 PF-20, Appendix A.1 |
| Prompt body ≤ 7000 Unicode code points, export newline excluded | §9.1, PF-09, §10.1 |
| Speaker IDs `(S1)`… assigned in order of first vocal event (app-computed) | §9.5 |

---

### 6.4 Row mapping, labels, defaults, and revisions

JSON field names are the column names in §6.1. The API rejects unknown fields with `422` and code `validation`. `selected_prompt_id` has **no** SQL foreign key, because `prompts` also references `clips`. The repository accepts it only when the prompt row exists and its `clip_id` matches, and sets it to null when that prompt is deleted.

**Where each mode stores pictures and media**

| Mode | `references_tokens` | Subjects, shots, retention |
|---|---|---|
| T2VA | none | none. The shot plan lives only in `prompts.structured_payload_json`. |
| I2VA | exactly one `image`, `role_hint = first_frame`, position 1, label `<Picture 1>` | none |
| L2VA | exactly one `image`, `role_hint = last_frame`, position 1, label `<Picture 1>` | none |
| FL2VA | exactly two `image` rows. Position order is first frame then last frame. `role_hint` is `first_frame` then `last_frame`. Labels `<Picture 1>` and `<Picture 2>` | none |
| REF2VA | any mix inside the §6.3 budgets. `role_hint` is empty; roles live on `subject_pictures` | required as §4.4.6 |

The repository rejects a reference whose kind the mode does not allow. The API accepts audio and video duration as seconds with at most three decimal places and stores `duration_ms = round(seconds * 1000)`. Later checks add those integers. They do not compare floats. NaN and infinite values are `422`. Reference tokens are lightweight prompt metadata tokens (`<Picture N>`, `<Audio N>`, `<Video N>`). Image width and height are optional metadata. Incomplete or omitted width/height values do not block generation or export. If supplied, values outside 256–5760 px or ratio [0.4, 2.5] emit advisory warnings (PF-20). Durations for audio and video (2000–15000 ms) remain strictly validated. Subjects may link to 0, 1, or multiple reference pictures via `subject_pictures`. A subject with 0 linked pictures is compiled as a text-only description. A subject with 1 picture links an identity anchor or other role. A subject with multiple pictures links distinct aspects (e.g. identity anchor from `<Picture 1>` and outfit from `<Picture 2>`).

**Labels.** Image ordinals, video ordinals, and audio ordinals are numbered separately in `position` order, starting at 1. The label is `<Picture N>`, `<Video N>`, or `<Audio N>`. Subject labels use `subjects.ordinal`. Reordering rewrites `position` to `1..n` and recomputes ordinals. SQLite unique constraints are updated by shifting ordinals and positions by a temporary positive offset (e.g. `+1000000`), then writing the final sequential numbers, in one transaction (§6.4).

**Create-clip defaults**, when the body omits a field: `h3_model`, `style_id`, `language`, and `audio_policy` come from the settings resolution chain; `duration_s` is 8; `resolution` is `768P`; `ratio` is `16:9` for T2VA and `adaptive` otherwise; `name` is `Clip`. Creating an FL2VA clip sets `requested_shot_count` to 1. Other modes leave it null, which means the planner chooses a count inside the §A.4 minimum and maximum.

**Mode change** is one transaction. It deletes references, subjects, pictures, shots, speakers, lines, on-screen texts, retention rows, and prompts; resets `ratio` to the mode default; sets `requested_shot_count` to 1 for FL2VA and null otherwise; increments `revision` and `inputs_revision`. The UI asks the user to confirm before sending it.

**`inputs_revision`** increments when any of these clip columns change: `mode`, `h3_model`, `style_id`, `plain_style_pair`, `duration_s`, `resolution`, `ratio`, `language`, `audio_policy`, `seed_text`, `action_text`, `custom_soundscape`, `custom_music`, `task_types_json`, `requested_shot_count`, `manual_draft`, `manual_template`. It also increments when any row in `references_tokens`, `subjects`, `subject_pictures`, `shots`, `speakers`, `dialogue_lines`, `onscreen_texts`, or `retention_markers` is inserted, updated, or deleted. `name` and `wizard_step` do not increment it. `revision` increments on every successful clip or child write, including a name change.

**Shots.** The user supplies `start_ms` for shot 2 onward. Shot 1 is always `start_ms = 0`. The repository writes `end_ms`: the next shot's `start_ms`, or `duration_s * 1000` for the last shot. Starts must be strictly increasing and the last `end_ms` must equal the duration. `pacing` is `silent` or `action`. A shot that owns a dialogue line uses the line formula in §9.5 and ignores `pacing`.

**Speakers and lines.** `voice_source` is empty, a library id (`F1`–`F10`, `M1`–`M11`, `K1`, `K2`), or a short prose phrase. `audio_reference_id`, when set, wins over `voice_source` and always renders the timbre phrase from the audio row's **current** ordinal. `speaker_id_2` is the second speaker of one shared utterance; the rendered tag is `(S1,S2)` in assigned-id order. `dest_shot_id` is required when `crosses_cut = 1` and must differ from `shot_id`. `gloss` is optional English for the model; it is never copied into the prompt. `delivery` is one of the ids in Appendix A.8.

**Retention identity.** A marker points at a `subject_id` or a `reference_id`, never a label string. Sync, inside the render step, upserts one row per subject, per anchor picture (frame, composition, or framing role), per video, and per audio. It preserves `marker`, `reason`, `marker_source`, `parenthetical`, and `shot_ordinals_json` when the same subject or reference already has a row. New rows use the defaults in §8.6 and an empty reason. Deleted subjects and references cascade their markers.

**Task types.** `task_types_json` is a JSON array. On write the repository drops duplicates and sorts into this order: `reference generation`, `keyframe completion`, `video editing`, `video continuation`, `audio reuse`, `audio reference`. While `task_types_touched = 0`, a reference or picture-role change recomputes the defaults in §8.5. The first user edit of the checklist sets `task_types_touched = 1` and stops that recompute.

### 6.5 Status values

`clips.status` describes the selected prompt:

| Value | Meaning |
|---|---|
| `draft` | No current render, or a generation-relevant edit happened after the last render. |
| `generating` | This clip holds the process lock. |
| `preflight` | The selected prompt has no blocking violation and `fixer_retries = 0`. |
| `fixed` | The selected prompt has no blocking violation and `fixer_retries > 0`. |
| `blocked` | The selected prompt has a blocking violation. |
| `failed` | The pipeline stopped on a stage error. Partial rows are kept. |
| `exported` | The selected prompt was exported and nothing generation-relevant has changed since. |

Transitions: an accepted generate sets `generating`; cancel, client disconnect, or startup recovery sets `draft` (startup rewrites every `generating` row). A stage error sets `failed`. A finished render sets `preflight`, `fixed`, or `blocked` from the rule above. A generation-relevant edit sets `draft`. `/select` recomputes `preflight`, `fixed`, or `blocked` from the newly selected prompt and does not call the model. Export sets `exported` only after the files and the database update commit. `POST /preflight` refreshes `preflight_json` and does not by itself change `status`. Recording an explicit override via `POST /override` that removes the last blocking violation on the selected prompt transitions `clips.status` to `preflight` (or `fixed` if `fixer_retries > 0`).

---


## 7. Module Specifications

### 7.1 Generator tab shell

- Renders mode tabs from `GET /api/modes`; shared clip metadata bar.
- **Mode hint**, from Appendix A.1: use I2VA when one image is the exact opening frame; move to REF2VA when a face that matters is hidden or turned, an unlisted person appears, the camera reveals a new side, or an audio/motion reference is required. The hint never changes the tab by itself. I2VA, FL2VA, and L2VA reject `<Subject>`, `<Audio>`, and `<Video>` tokens. REF2VA rejects an I2VA, FL2VA, or L2VA instruction line.
- **Style.** `plain` = one allowed pair from Appendix A. Named styles insert the exact opening defined there: 80s Bollywood, cinematic modern, modern series, or noir thriller. REF2VA uses the defined `The target video is …` sentence; T2VA/I2VA/FL2VA/L2VA use the defined `[Shot 1]` opening. The house audio rule overrides any music/ambience suggested by a style.
- **Ratio widget** per mode: T2VA concrete select; I2VA/FL2VA/L2VA locked `adaptive`; REF2VA `adaptive` default with optional concrete ratio. Settings default ratio applies only where the mode allows it.
- **Duration** slider from the model minimum through 15. **Resolution** lists only that model's values. **Language** from `languages.json`.
- The mode-specific instruction line is **rendered by the app** (I2VA/FL2VA/L2VA); T2VA has none.

### 7.2 T2VA module

- Input: `seed_text` + optional dialogue lines + `audio_policy` (+ optional manual draft).
- Pipeline: `seed_elaboration` (skipped if manual) → `prose_writer` → render → preflight.
- Output contract: exactly three fields, blank line between, one continuous paragraph in `integrated_multimodal_description`, `[Shot 1]` untimed, concrete ratio in the preview metadata block only (never inside the file). Style opening per §7.1. The renderer appends the house audio sentence (dialogue-only) and expands voice placeholders.

### 7.3 I2VA / FL2VA / L2VA modules

- Shared machinery, three variants. Input: frame token(s), caption(s), typed `width_px`/`height_px`, `action_text`, dialogue/audio policy.
- Pipeline: `frame_action_elaboration` → `prose_writer` → render (computes `N`, `S.SS`, instruction line) → preflight.
- Guards: one image for I2VA/L2VA, two for FL2VA; `adaptive` locked; no `<Subject>`/`<Audio>`/`<Video>` tokens. FL2VA may be one shot.
- Image dimension rules (256–5760 px per side, ratio 0.4–2.5) apply to frame images too (PF-20).

### 7.4 REF2VA module

1. **Reference Tokens** — §4.4.6. Lightweight metadata tokens; optional dimensions; hard counts (≤ 9 pictures, ≤ 3 videos, ≤ 3 audio, ≤ 12 files).
2. **Subjects & Picture Links** — many-to-many mapping: 0 pictures (text-only), 1 picture (identity anchor), or multiple pictures (e.g. face anchor + outfit reference).
3. **Shot Editor** — shots with exact start times; `end_ms` app-written; dialogue lines with speaker and audio links. Two people speaking together use one line tagged `(S1,S2)`.
4. **Action Bar & Retention** — `subject_defs` (deterministic) → `shot_writer` → `summary_writer` → `retention_writer` → render → preflight. Output is the six sections in exact order defined in §7.6. `detailed_description` target is 350–500 words; style sentence(s) start `The target video is …` before `[Shot 1]`.

REF2VA hard contracts beyond the PF list: the `summary` prefix is one bracketed task type, or several joined by ` + ` inside one pair of brackets, never repeated (e.g. `[reference generation + audio reference]`). No `(Sx)` in `retention_analysis`. No new labels in `summary`. Every label is defined once in `subject_definitions`. Person, location, outfit-only, prop, picture-anchor, and audio-reference formulas are specified in Appendix A.9. Input images are identified by their reference role and are not described beyond what is needed to name the subject. Frame-anchor phrases: `the shot begins from <Picture 1>`, `the shot's keyframe corresponds to <Picture 2>`, `the shot ends on <Picture 3>`. Speaking subjects are `<Subject N> (Sx)`. Cut wording is `the camera cuts to`.

### 7.5 Settings module

Per §4.4.7. There is no LLM-assembler control. Persistence is the `settings` table plus `projects.default_settings`. Changes apply to new clips; the active clip keeps its values unless the user chooses "apply to active clip". The drafter must be one of the names returned by Ollama `GET {endpoint}/api/tags`. The H3 video model is a two-value control, not an Ollama tag.

| Settings key | Default |
|---|---|
| `ollama_endpoint` | `http://127.0.0.1:11434` |
| `drafter_model` | empty until the user picks a prefetched tag |
| `temperature` | `0.2` |
| `num_ctx` | `8192` |
| `timeout_s` | `120` |
| `keep_alive` | `10m` |
| `seed_mode` | `auto` (`fixed` uses `seed_value`) |
| `seed_value` | `0` |
| `max_fixer_retries` | `2` |
| `h3_model` | `MiniMax-H3` |
| `default_duration_s` | `8` |
| `default_resolution` | `768P` |
| `default_ratio` | `16:9` (applied only when the mode allows it) |
| `default_style_id` | `plain` |
| `default_plain_style_pair` | `Live-action, cinematic` |
| `default_language` | `English` |
| `default_audio_policy` | `dialogue_only` |
| `export_directory` | `/home/wizdroid/Applications/h3-mechanic/data/exports` |
| `listen_port` | `9013` (integer 1–65535; §5.7) |
| `collision_policy` | `auto_increment` |
| `theme` | `nord-dark` (`nord-coloured` or `nord-light`) |

`default_settings` may set `h3_model`, `duration_s`, `resolution`, `ratio`, `style_id`, `plain_style_pair`, `language`, and `audio_policy`. Absent keys fall through. `listen_port` is process-global. It is not part of `default_settings` and it does not follow the clip-value chain.

### 7.6 Output layout contract and sentence forms

- **T2VA / frame modes:** `field_name: content` on one line with exactly one space after the colon; one blank line between fields; no trailing spaces; `integrated_multimodal_description` is a single paragraph with shots inline. Frame modes: the instruction line, one blank line, then the fields.
- **REF2VA:** each `section_name:` header alone on its line, content on the following lines, blank line between sections. `subject_definitions` and `retention_analysis`: one entry per line. `summary`: bracketed prefix and paragraph on one line. `detailed_description`: style sentence(s) on the first line, then each `[Shot N]` on its own line. Soundscape and music: one paragraph each.
- **Speech sentences** are only the §8.0 expansion of `{{Lk}}`. The model does not write speaker tags, voice phrases, accents, delivery, dialogue text, or `{{V:…}}`.
- REF2VA `first_frame`/`keyframe`/`last_frame` picture links are **prompt-level anchors**; the app never emits API roles and never mixes them with frame-mode instruction lines.
- Under `dialogue_only` the renderer inserts `The audio contains only the spoken dialogue, with no background music, no ambience, and no sound effects.` exactly once. In REF2VA it is the last sentence of the style line, before the newline that starts `[Shot 1]`. In other modes it is inserted immediately after the first sentence of `[Shot 1]`. Under `custom` or `silence` that sentence is absent.
- UI hint (non-blocking): readable faces on `MiniMax-H3` suggest `2K`; rear wides tolerate `768P`.

---

## 8. Meta-Prompt Engineering

All prompts live in `llm/prompt_bank.py`. Conventions: `{{var}}` placeholders; output-shape contract on line 2; no examples unless the shape is ambiguous; imperative single clauses; rules injected per stage from application resources — a stage receives only the clauses required for that stage.

| Stage id | Used by | Output shape | Ollama `format` |
|---|---|---|---|
| `seed_elaboration` | T2VA | JSON | JSON Schema (fallback `"json"`) |
| `frame_action_elaboration` | I2VA, FL2VA, L2VA | JSON | JSON Schema (fallback `"json"`) |
| `prose_writer` | T2VA, I2VA, FL2VA, L2VA | plain text (template body) | text |
| `subject_defs` | REF2VA | **deterministic** (no LLM) | — |
| `shot_writer` | REF2VA | plain text (section body) | text |
| `summary_writer` | REF2VA | plain text | text |
| `retention_writer` | REF2VA | JSON `{reasons:[…]}` | JSON Schema |
| renderer (assembler) | all | deterministic Python | — |
| `preflight_fixer` | all (fixable violations) | template text | text |
| `safer_framing` | all (optional) | template text | text |

### 8.0 Placeholder protocol

Native-script dialogue, voice paste phrases, delivery wording, speaker ids, and on-screen text are **never given to the model to copy**.

Number dialogue lines `k = 1..n` by `(shot.start_ms, line_order, line id)`. The template contains `{{Lk}}` for each, spelled exactly that way (`{{L1}}`, `{{L2}}`, …). Number on-screen texts by `onscreen_texts.ordinal` as `{{Tm}}`. The model does not emit `{{V:…}}`.

**Integrity, checked on the template before render:**

- every `{{Lk}}` appears exactly once, and the `k` sequence in the template is strictly increasing;
- for REF2VA, `{{Lk}}` sits in the shot whose id is that line's `shot_id`;
- every `{{Tm}}` appears exactly once, and no other `{{` token exists;
- a manual or model template that contains `{{V:` fails this check.

**`{{Lk}}` expands to one speech sentence.** The renderer builds it. The model only places the token.

1. Speaker reference. REF2VA with a subject: `<Subject N>`. REF2VA without a subject: the persona. Other modes: `The {persona}` unless the persona already starts with `the ` (compared case-insensitively). Two speakers: `{ref1} and {ref2}`.
2. Tag. One speaker: ` (S{n})`. Two speakers: ` (S{a},S{b})` with the smaller assigned number first.
3. Verb. Voiceover: `says in an off-screen voiceover`. Otherwise the verb from Appendix A.8 for `delivery` (`none` uses `says`).
4. Voice phrase. If `audio_reference_id` is set: `in the voice timbre referenced from <Audio N>` using that row's current ordinal. Otherwise the library paste phrase, or the user's prose with a leading `in ` added when the prose does not already start with `in `.
5. Accent. If `accent` is not empty: `, {accent}`. The stored value is the exact clause from Appendix A.7, or empty.
6. Manner. If Appendix A.8 lists a manner for the delivery: `, {manner}`.
7. Dialogue. A cross-cut line inserts `<scenetrans>` immediately before `<d>`. Then `<d>[{Language}] {normalised text}</d>`. A cutoff line inserts `<cutoff>` immediately after `</d>`.
8. Closure. Voiceover, including a voiceover that is also cut off: ` while {pronoun} lips remain completely closed`. A non-voiceover line that is not cut off ends the sentence, and the next sentence is `{He|She|It} closes {his|her|its} lips.` Two speakers use `Both speakers close their lips.` Pronoun `his` → `He`/`his`, `her` → `She`/`her`, `its` → `It`/`its`. The pronoun comes from the linked subject when `subject_id` is set, otherwise from the speaker. The repository copies the subject pronoun onto the speaker when it saves a linked speaker.

A two-speaker line is one shared utterance with one `<d>` span. The rendered body repeats the full voice phrase on every line of that speaker. It does not switch to `in the same … voice`.

**Cross-cut destination.** The source shot contains the expanded `{{Lk}}` only. The renderer also prefixes the destination shot, once. For Shot 1 ($N = 1$), it prefixes the shot body with `<scenetrans> The audio continues seamlessly across the cut. `. For $N > 1$, the prefix is placed immediately AFTER the cut header: `[Shot N] At MM:SS.mmm, the camera cuts to <scenetrans> The audio continues seamlessly across the cut. `, ensuring that the cut timestamp pattern (`CUT_TIME_RE`) remains intact at the start of the shot line.

**`{{Tm}}`** expands to `"text_raw"` using straight double quotes (U+0022). The renderer does not translate or trim interior spaces.

**After expansion** the body contains no `{{` and no `}}`. A remainder is PF-28.

The model receives, per line, only `k`, the speaker display name, the language name, the delivery id, and the gloss. An empty gloss is passed as `meaning unknown`. `text_raw` is not in the request.

**Plan object.** For REF2VA, `{{plan}}` is the deterministic JSON of subjects (label, role phrase, pronoun, picture links), shots (ordinal, start time, size, angle, move, pacing, events), lines (`{{Lk}}` plus speaker labels, not `text_raw`), and references (labels and captions). `engine/placeholders.py` produces it. It is the only creative input to the REF2VA model stages. For T2VA and frame modes the plan is the JSON returned by `seed_elaboration` or `frame_action_elaboration` after schema validation. Speaker keys in that JSON are `str(speakers.id)`, never `S1`.

**Voice write-back.** When `voice_source` is empty and `audio_reference_id` is null, the plan's `voices` entry for that speaker key must be a library id. The repository saves it before `prose_writer` or `shot_writer` runs. An id outside Appendix A.7 is a stage failure, not a silent substitution. Manual draft has no plan, so Stage 0 requires a library id, prose, or an audio reference.

**Fallback flag.** When §8.1b uses the stitched fallback, `prompts.prose_fallback = 1`. Otherwise it is 0.

### 8.1 Seed elaboration (T2VA)

```
Expand a brief into a scene plan for a video AI. Reply JSON only, matching the schema.
Seed: {{seed}}  Duration: {{duration_s}}s  Ratio: {{ratio}}  Style opening: {{style_opening}}
Lines (placeholders only): {{line_stubs}}   Voice library ids: {{voice_ids}}
Keys: characters, setting, beats, shots, voices.
Rules: beats are causal chains (initial state, trigger, action, reaction). shots: count per {{shot_budget}}; each has start_s, end_s, size, angle, pacing, camera_phrase from {{verbs}} with landing, and line_ids. voices: one library id from {{voice_ids}} per speaker. Do not invent prose voices. Prose is English. Max 320 words.
```


`{{shot_budget}}` is `requested_shot_count` when that value is set. Otherwise it is the planner target from Appendix A.4, and the prompt also states that table's minimum and maximum. A plan whose shot count disagrees with a set `requested_shot_count`, or which falls outside the legal range, is a stage failure. `{{verbs}}` is the official phrase list in §9.6. `seed_elaboration` must validate against this schema before write-back. `additionalProperties` is false. Frame plans use the same schema with the extra checks in §8.2.

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "characters",
    "setting",
    "beats",
    "shots",
    "voices"
  ],
  "properties": {
    "characters": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "speaker_key",
          "persona"
        ],
        "properties": {
          "speaker_key": {
            "type": "string"
          },
          "persona": {
            "type": "string",
            "maxLength": 80
          }
        }
      }
    },
    "setting": {
      "type": "string"
    },
    "beats": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "shots": {
      "type": "array",
      "minItems": 1,
      "maxItems": 4,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "start_s",
          "end_s",
          "size",
          "angle",
          "camera_phrase",
          "pacing",
          "line_ids"
        ],
        "properties": {
          "start_s": {
            "type": "number"
          },
          "end_s": {
            "type": "number"
          },
          "size": {
            "type": "string"
          },
          "angle": {
            "type": "string"
          },
          "camera_phrase": {
            "type": "string"
          },
          "landing": {
            "type": "string"
          },
          "pacing": {
            "enum": [
              "silent",
              "action"
            ]
          },
          "events": {
            "type": "string"
          },
          "action_chain": {
            "type": "string"
          },
          "expression": {
            "type": "string"
          },
          "line_ids": {
            "type": "array",
            "items": {
              "type": "string"
            }
          }
        }
      }
    },
    "voices": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "speaker_key",
          "voice"
        ],
        "properties": {
          "speaker_key": {
            "type": "string"
          },
          "voice": {
            "type": "string"
          }
        }
      }
    }
  }
}
```

**Reasoning:** Schema-constrained JSON plus an explicit key list removes fence-parsing failures. Lines are passed as stubs (id, speaker, language, delivery), never as native-script text, so there is nothing to corrupt. The shots array carries timing and framing so the renderer computes `MM:SS.mmm` and the validator can pre-check PF-03/PF-05 on structured data before any prose exists.

### 8.1b Prose writer (T2VA / I2VA / FL2VA / L2VA)

```
Write the shots of a video prompt from this plan: {{plan_json}}. Style opening: {{style_opening}}
Output the integrated_multimodal_description paragraph only. Start with the style opening, then [Shot 1] (untimed), then for each later shot "[Shot N] At {{cut_time_n}}, the camera cuts to".
Per shot: framing and subject position, light, one causal action chain with physical feedback, exactly the planned camera move with landing, an expression for each readable face, and each planned line only as {{L1}}. Do not write a speaker, a voice, a delivery, mouth closure, or any non-English text. {{L1}} expands to the speech sentence. No sound descriptions. {{mode_path_rule}}
Target {{word_target}} words. Plain text, one paragraph.
```

`{{mode_path_rule}}`: I2VA — anchor → onset → development → result; FL2VA — describe motion *between* the frames, final shot lands on the last frame; L2VA — precede, act, converge, land on the last frame. `{{cut_time_n}}` values are pre-formatted by the renderer's formatter (never by the model).

`{{precision_rules}}` (defined in Appendix A and injected as compressed clauses; also into `shot_writer`): expand actions into causal chains with physical feedback; camera = position + movement + direction + speed/amplitude + subject followed; emotions as observable micro-actions (gaze, brows, lips, breath, hands), never abstract labels; faces: CU/MCU at 85mm, MS at 50mm, centered, `steady distance` on tracking shots with faces, arrivals stop in a clear medium framing; carry state (damage, props, screen direction) across shots; no filler tags. Each rule is a single imperative; the stage receives only the clauses relevant to the planned shots.

**Reasoning:** Separating *planning* (structured, small, validated) from *writing* (free text) gives local models one job per call and gives the validator structured data to cross-check the prose against (planned camera verb vs. written verb). If `prose_writer` fails twice and the plan is schema-valid, `fallback_prose` stitches one paragraph and sets `prompts.prose_fallback = 1`. Shot 1 starts with the Appendix A.10 prefix. Each later shot starts `[Shot N] At {time}, the camera cuts to `. The shot then adds the planned size phrase, angle phrase, events or action chain, official camera phrase, landing, and that shot's `{{Lk}}` and `{{Tm}}` tokens, separated by single spaces. The fallback stitcher guarantees that all `{{Lk}}` and `{{Tm}}` placeholders belonging to each shot are preserved in the fallback text without omission. The UI says "Drafted without the prose model." REF2VA has no prose fallback. If the plan stage fails twice, there is no fallback either. `{{word_target}}` is 110 words at 4–6 s, 180 words at 7–10 s, and 260 words at 11–15 s.

### 8.2 Frame-action elaboration (I2VA / FL2VA / L2VA)

```
Mode: {{mode}}. Frames: {{frames}}. Action: {{action}}. Duration: {{duration_s}}s. Style opening: {{style_opening}}
Lines (placeholders only): {{line_stubs}}
Write the motion plan as JSON shots. Use exactly {{shot_count}} shots. I2VA: from frame state → onset → development → result. FL2VA: describe motion between the frames; the final shot lands on the last frame. L2VA: precede, act, converge onto the last frame.
Per shot: start_s, end_s, composition, action_chain, camera (one verb from {{verbs}} with direction and landing), expression per readable face, line placeholders. First shot starts 0.0. Prose is English. Max 260 words.
```

**Reasoning:** One prompt parameterised by mode. `{{shot_count}}` is `requested_shot_count`, and FL2VA uses 1 when that value is null (§6.4). The PF-03 minimum is waived only for that one-shot case. Times are formatted by code, which avoids the `00:03:000` typo. A frame plan uses the §8.1 schema with `characters` equal to `[]`, `setting` equal to `""`, and `beats` equal to `[]`. The app then rejects the plan unless every shot has a non-empty `action_chain` and `expression`, and unless the shot count equals `{{shot_count}}`.

### 8.3 Subject definition builder (REF2VA) — deterministic

Generated in Python from `subjects`, `subject_pictures`, and speaker audio links. **No LLM call.** The deterministic builder supports:
- **0 pictures linked:** `<Subject N> is the {role_phrase}[, {appositive},] with {pronoun} appearance, facial features, build, and complete {outfit_noun} defined by text alone.`
- **1 picture linked:** Standard identity anchor formula: `<Subject N> is the {role_phrase} in <Picture M>[, {appositive},] with {pronoun} face, hair, build, and complete {outfit_noun} taken exactly from the reference.`
- **Multiple pictures linked:** Dual/multi-anchor formula combining face/identity and outfit: `<Subject N> is the {role_phrase} with {pronoun} face, hair, and build taken from <Picture M>[, {appositive},] and {pronoun} complete {outfit_noun} taken from <Picture P>.` Additional roles (props, locations) emit their corresponding lines.
Picture anchor lines (`<Picture N> is the {role} for [Shot X], defining {defines_text}.`) and audio lines (`<Audio N> is the voice-timbre reference for <Subject N> (Sx).`) follow Appendix A.9. A missing `role_phrase` fails Stage 0. Suggest-role is the separate route in §5.6: one call, JSON `{role_phrase}` of at most four words, noun only, no visual description, and no write until the user saves it.

**Reasoning:** The formula is fixed text; spending LLM tokens on it only adds the risk of "his/her", visual descriptions and drifting wording (the main PF-23 failures). Anchor discipline is enforced by construction.

### 8.4 Shot writer (REF2VA)

```
Write detailed_description for the plan: {{plan}}. Style sentence: {{style_opening}}
Put the style sentence before [Shot 1]. It starts "The target video is".
Per shot: "[Shot 1]" alone; "[Shot N] At {{cut_time_n}}, the camera cuts to" for N>1 (use the given times exactly).
Content per shot: composition and size, subject labels, light, one causal action chain with physical feedback, the planned camera move with landing, an expression per readable face, and each line only as {{Lk}}. Do not write a speaker tag, a voice, a delivery, mouth closure, or any quoted or non-English text.
Readable or speaking faces: close-up/medium close-up/medium, front or three-quarter; wide only from behind or with no readable faces.
{{audio_policy_line}}
Target {{word_target}} words. Plain text.
```

**Reasoning:** Carries the cross-cutting precision rules in compressed imperatives. Timestamps and speaker IDs are pre-computed and given, so the model only copies them. The word target (350–500) is specified in §7.4. With `num_ctx = 8192` the plan (~600–900 tokens) plus ~700-token output fits comfortably.

### 8.5 Summary writer (REF2VA)

```
Write the summary for labels {{labels}} and plan {{plan}}.
Write only the paragraph. The app adds the bracketed task-type prefix. Use only labels already defined: who, where, what happens, shot flow, each reference's contribution. No new labels. No bracket prefix. Max 90 words. Plain text.
```

The task-type prefix is **pre-selected by code** from the reference set and picture roles using the triggers in Appendix A.9 (`clips.task_types_json`): defaults — any guidance-only reference ⇒ `reference generation`; any `first_frame`/`keyframe`/`last_frame`/`composition_anchor` link ⇒ `keyframe completion`; audio used only for timbre ⇒ `audio reference`. `video editing`, `video continuation` and `audio reuse` are **never auto-selected**; the user ticks them (Step 4) and Stage 0 requires ≥ 1 video (editing/continuation) or audio (reuse). The mere presence of video/audio creates no task type. When `video editing` is chosen, the summary paragraph opens `The target video is an edited version of <Video K>.`, where K is the lowest video ordinal. `video continuation` adds no fixed sentence. The renderer writes the bracket prefix and, for editing only, that sentence. It strips a leading bracket prefix, or a mismatched editing sentence, from the model paragraph before prepending. Reasoning: the prefix is a closed-vocabulary decision; code decides it, the model writes only the paragraph.

### 8.6 Retention analysis writer (REF2VA)

Markers are chosen in the Step 4 table or defaulted: person, location, and `other` subjects, plus every picture anchor, use `fully_preserved`; outfit and prop subjects use `partially_preserved`; every video uses `weak_reference`; audio selected as `audio reuse` uses `fully_copy`; every other audio uses `reference`. `attribute_transfer`, `partially_copy`, and `partially_preserved` on a person are user choices only. Entries exist for every subject, every anchor picture (frame/composition/framing roles), every video and every audio. Sync rows as §6.4 describes before the model call. The model writes a reason only for a row whose reason is empty, at most 25 words, and it does not change markers. When every reason is already non-empty, skip the call:

```
For each entry give a reason, ≤ 25 words, no (Sx), no new labels. Reply JSON {"reasons":["…"]} in the same order. Entries: {{entries}}
```

The renderer builds each line from the fixed shapes: `<Subject N> (appears in [Shot 1], [Shot 3]): marker - reason.` / `<Picture N> ([Shot X] {first frame|keyframe|last frame|composition anchor|framing reference}): marker - reason.` / `<Video N> ({parenthetical, default "cut and pacing structure"}): marker - reason.` / `<Audio N>: marker - reason.` Reasoning: PF-22 (valid markers, no `(Sx)`) passes by construction; the LLM only writes prose reasons.

### 8.7 Final assembler (renderer)

Deterministic Python (`engine/renderer.py`) is the only assembler in v1; the optional "LLM assembler" setting of v1.2 is **removed** (it can only reintroduce errors the renderer prevents). Renderer jobs:

1. Compute shot count `N` and, for I2VA, FL2VA, and L2VA, the instruction line from Appendix A.2. `S.SS` is `str(duration_s) + ".00"`.
2. Format cut times as `MM:SS.mmm` from integer milliseconds (§9.5).
3. Assign `(Sx)` numbers per §9.5, then expand `{{Lk}}` and `{{Tm}}` per §8.0. Do not add a second speech sentence.
4. Insert the Appendix A.10 style prefix and the house sentence at the §7.6 position. Fill the sound fields from `audio_policy`.
5. Normalise whitespace to one blank line between sections or fields and no trailing spaces. Set `char_count` to the number of Unicode code points in `body`.

### 8.8 Preflight fixer

```
Fix this {{mode}} prompt template. Violations: {{violations}} (each with the exact rule and, where available, suggested_text).
Apply only these fixes. Keep every {{...}} placeholder, shot header, timestamp, label and unflagged sentence unchanged. Output the fixed template only.
```

**Reasoning:** The fixer sees only the violation list and edits the *template*, so verbatim content cannot be damaged; the integrity guard (§5.5) rejects any rewrite that changes the placeholder multiset or unflagged headers. Structural violations with `suggested_text` (e.g. timestamp format, missing house sentence) are first attempted by a **deterministic auto-repair** (`rules/*.py::autofix`) before spending an LLM call.

### 8.9 Safer framing

One button, `POST /api/clips/{id}/variations`. `409 Conflict` if a variation already exists in the same `generation_id`.

```
Rewrite only shot size and angle in this {{mode}} prompt template.
Move every readable or speaking face to a close-up, medium close-up, or medium shot, front-facing or three-quarter.
Keep every {{...}} placeholder, speaker id, label, timestamp, field name and camera verb unchanged.
Output the full template only.
```

Stored as a second `prompts` row (`stage = 'variation'`) with the same `generation_id`; preflight runs on it; export uses it only when selected via `/select`. Regenerating the draft starts a new `generation_id`.

---

## 9. Validation / Preflight Rules

Hard constraints defined in this specification are implemented in `validation/rules/`. `error` blocks export (unless explicitly overridden where permitted); `warning` annotates only. `Basis` = S (structural) or H (heuristic). `Ovr` = overridable. The severity in the tables below is the rule's maximum. PF-02, PF-04, PF-08b, and PF-12 may emit a warning for the subcase named in the row. Export blocks only on a violation whose emitted severity is `error` and which is not overridden.

### 9.1 All modes

| ID | Rule | Sev | Fix | Basis | Ovr | Normative basis |
|---|---|---|---|---|---|---|
| PF-01 | Field names/template exactly match the mode: T2VA → `integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music`, no instruction line; I2VA/FL2VA/L2VA → verbatim instruction line then the same three fields; REF2VA → six sections in order `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`; **layout (§7.6):** T2VA/frame fields are `name: content` on one line with `integrated_multimodal_description` as one paragraph; REF2VA headers `name:` stand alone with content on the following lines | error | yes | S | no | §9 and Appendix A |
| PF-02 | `[Shot 1]` has no timestamp. Later shots match `At MM:SS.mmm, the camera cuts to`, strictly increasing and below the duration. `MM:SS.mmm` is two minute digits, two second digits, a dot, and three millisecond digits. `At 00:03:000` is an error and is autofixed. A legal timestamp followed by `the shot cuts to` is a warning and is autofixed to `the camera cuts to`. Any other cut wording is an error | error | yes | S | no | §9.6, Appendix A.3 |
| PF-03 | Shot count lies between the Appendix A.4 minimum and maximum inclusive. FL2VA with `requested_shot_count` 1 waives the minimum only. A non-null requested count must equal the shot count and obey that same bound. Per-shot length uses §9.5. Starts and ends partition `[0, duration_s * 1000]` with no gap | error | yes | S | no | §9.5, Appendix A.4 |
| PF-04 | Exactly one official camera phrase per shot, matched by §9.6. A required move needs a landing substring ` toward `, ` revealing `, ` onto `, or ` as `. A missing landing on Static, POV, or Shake is a warning; a landing there is allowed. Any modifier (`with small amplitude`, `with large amplitude`, `at slow speed`, `at fast speed`) on Static, POV, or Shake is an error. The only allowed modifiers on other moves are those four phrases; any other modifier phrase is an error. The REF2VA style line contains no camera phrase | error | yes | H | yes | §9.6, Appendix A.5 |
| PF-05 | The §9.6 face heuristic: readable or speaking faces are close-up, medium close-up, or medium, front-facing or three-quarter, with a physical expression token and mouth closure. POV must say the face is not visible. Wide-angle and action-cam phrases fail on a face shot | error | yes | H | yes | §9.6, Appendix A.4 |
| PF-06 | Every rendered speech sentence equals the §8.0 expansion, including tag order, voice phrase, accent, manner, `<d>` text, `<scenetrans>`, `<cutoff>`, and lip closure. Speaker numbers follow §9.5. A bare library id such as `F3` is an error. The same speaker repeats the same voice phrase on every line | error | yes | S | no | §8.0, §9.5 |
| PF-07 | Dialogue verbatim, native script, inside `<d>[Language] …</d>`, ending `.`, `?` or `!` (not `।`); span text equals stored `text_raw` (after §9.5 normalisation). On-screen text in `"double quotes"`, verbatim. A cross-cut line has `<scenetrans>` immediately before `<d>` in the source shot; in the destination shot ($N > 1$), `<scenetrans> The audio continues seamlessly across the cut. ` follows immediately after the cut header (`[Shot N] At MM:SS.mmm, the camera cuts to <scenetrans> ...`); `<cutoff>` for a video-end cut-off line; those tags are absent otherwise | error | yes | S | no | §8.0, Appendix A |
| PF-08 | `dialogue_only` and `silence`: both sound fields are exactly `N/A`. `custom`: soundscape is 1–4 sentences and not `N/A`; music is 1–3 sentences or exactly `N/A`. Sentence count uses §9.6. The house sentence is PF-35, not this rule | error | yes | S | no | §7.6, Appendix A.3 |
| PF-08b | In `non_diegetic_music` only, `tense` and `sad` are errors and the other §9.6 mood words are warnings. Whole-word, case-insensitive. A non-Latin `text_in_prompt` must not appear outside its `<d>` span | error | yes | S | no | §9.6, Appendix A.11 |
| PF-09 | `body` ≤ 7000 Unicode code points. The export newline in §10.1 is outside that count. Plain text only (no markdown/bullets) | error | yes | S | no | §10.1, Appendix A |
| PF-10 | All fields English; non-English only inside `<d>` and verbatim visible-text quotes. Detection: after removing `<d>…</d>` and `"…"` spans, any character in a non-Latin script block, or an Indic-language tag outside `<d>`, is a violation | error | yes | H | yes | §9 and Appendix A |
| PF-11 | T2VA ratio concrete (`21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`), never `adaptive`; I2VA/FL2VA/L2VA `adaptive` | error | no | S | no | §9 and Appendix A |
| PF-12 | Planned or stored shot ends partition `[0, duration_s * 1000]` with no gap and no overlap. Fewer than 12 whitespace-separated words in the last shot is a warning, not an error | error | yes | S | no | §6.4 |
| PF-13 | Video-model matrix (see §6.3). The Ollama drafter is not an input | error | no | S | no | §9 and Appendix A |
### 9.2 REF2VA-specific and cross-mode

| ID | Rule | Sev | Fix | Basis | Ovr | Normative basis |
|---|---|---|---|---|---|---|
| PF-20 | **Reference limits & budgets:** REF2VA budgets: images ≤ 9, videos ≤ 3, audio ≤ 3, files ≤ 12; each audio/video `duration_ms` present and 2000–15000; each type sums to ≤ 15000. **Image dimensions (advisory):** image width and height are optional metadata; if provided, dimensions outside 256–5760 px or ratio outside [0.4, 2.5] emit a non-blocking warning, never an export-blocking error. The file is never read | error | no | S | no | §6.1, Appendix A.1 |
| PF-21 | `summary` opens with one bracketed task type (or several joined by ` + ` in one bracket pair), selected from Appendix A.9, with no repeated type; no new labels in `summary` | error | yes | S | no | §9 and Appendix A |
| PF-22 | Retention markers valid: visual `fully_preserved`/`partially_preserved`/`attribute_transfer`/`weak_reference`; audio `fully_copy`/`partially_copy`/`reference`/`weak_reference`; no `(Sx)` in `retention_analysis` | error | yes | S | no | §9 and Appendix A |
| PF-23 | Every `<Picture N>`, `<Audio N>`, `<Video N>`, and `<Subject N>` is defined once and exists in the tables, and every reference row appears at least once. `subject_definitions` lines match the Appendix A.9 formulas (supporting 0, 1, or multiple linked pictures) in that section's order. Shot prose may describe the scene. This rule does not ban visual words outside `subject_definitions` | error | yes | S | no | Appendix A.9 |
| PF-24 | Style sentence(s) before `[Shot 1]`, starting `The target video is …` | error | yes | S | no | §9 and Appendix A |
| PF-25 | Speaking subjects written `<Subject N> (Sx)`; `<Audio N>` timbre-only refs carry no original words; audio relationships placed in the matching audible layer | error | yes | S | no | §9 and Appendix A |
| PF-26 | `detailed_description` 350–500 words (warning outside; dialogue-heavy clips prioritise fitting lines) | warning | no | S | n/a | §9 and Appendix A |
| PF-27 | T2VA contains no `<Picture>`, `<Subject>`, `<Audio>`, `<Video>` token; frame modes contain no `<Subject>`, `<Audio>`, `<Video>` token and no six-section header. REF2VA contains no I2VA/FL2VA/L2VA instruction line. Inside REF2VA, `first_frame`/`keyframe`/`last_frame` links are allowed as anchors | error | yes | S | no | §9 and Appendix A |
| PF-28 | Template integrity per §8.0: every `{{Lk}}` and `{{Tm}}` once, in order, and in the owning REF2VA shot; preserved across model drafts and fallback prose; no `{{V:`; no leftover `{{` in the body. `text_raw` was normalised only as §9.5 allows | error | yes | S | no | §8.0, §9.5 |
| PF-29 | **Plan–prose agreement** (T2VA/frame modes, when a plan exists): each shot's written camera verb equals the planned verb; written cut times equal planned times | error | yes | S | no | §8.0 and §9.5 |
| PF-30 | **Stale prompt:** `prompts.inputs_revision ≠ clips.inputs_revision`. Must regenerate; the fixer is not applicable | error | no | S | no | §8.0 and §9.5 |
| PF-31 | **Native-script input:** a line tagged with a non-English language must contain at least one letter/mark in the target script ranges in Appendix A.6 (Latin words allowed for code-mixed speech); a purely romanised line is input-required. A conversion helper may suggest native script but requires user confirmation. One language per line: a two-language utterance is two lines | error | no | S | no | §9 and Appendix A |
| PF-32 | On-screen text longer than 3 words, or any request for subtitles | warning | no | S | n/a | §9 and Appendix A |
| PF-33 | Filler/tag-stack words (`4k`, `masterpiece`, `high quality`, `epic`, `dynamic camera`, `cool VFX`) and abstract emotion labels with no observable cue (lexicon-based) | warning | no | H | n/a | §9 and Appendix A |
| PF-34 | Under `dialogue_only` or `silence`, shot prose hits the §9.6 sound lexicon after the house sentence, `<d>` spans, and quoted spans are removed. `custom` skips this rule | error | yes | H | yes | §9.6 |
| PF-35 | The house sentence in Appendix A.3 occurs once, at the §7.6 position, under `dialogue_only`, and occurs zero times under `custom` or `silence` | error | yes | S | no | §7.6 |

### 9.3 Fix-loop contract

Violations are normalized objects (§9.4). Order: (1) deterministic autofix for violations that carry an exact `suggested_text` rule; (2) LLM fixer only when all remaining blocking violations are `fixable == true`; (3) at most N retries (default 2); (4) remaining errors block export; warnings display only.

### 9.4 Required validator outputs and overrides

```json
[
  {
    "rule_id": "PF-21",
    "section": "summary",
    "severity": "error",
    "basis": "structural",
    "message": "Summary must open with one bracketed task type from Appendix A.9 with no repeated types.",
    "suggested_text": "[reference generation]",
    "blocking": true,
    "fixable": true,
    "overridable": false,
    "overridden": false
  }
]
```

The UI renders these but must not reinterpret them. The fixer and export gate consume the same objects. A violation is `fixable: true` only if the rule has a deterministic correction strategy, the correction does not change mode/model/reference budgets, and the app can verify the corrected prompt.

**Overrides.** Only rules with `basis == heuristic` and `overridable == true` (PF-04, PF-05, PF-10, PF-34) can be overridden, because pattern matching can misjudge valid prose. An override is an explicit user action (`POST /api/clips/{id}/override` with a mandatory note) recorded in `prompts.overrides_json` and shown in the exported JSON snapshot; it applies only to that prompt row and is invalidated by any later change to the prompt body. Structural rules can never be overridden. If any blocking violation has `fixable == false` and is not overridden (PF-11, PF-13, PF-20, PF-30), the LLM fixer is not invoked and export stays blocked until the user changes inputs.

### 9.5 Deterministic estimators and conventions

- **Speaker numbers.** Sort lines by `(shot.start_ms, line_order, id)`. A missing shot counts as start 0. Walk that list. The first time a `speakers.id` appears, assign the next number from 1. A two-speaker line assigns both at that position, in ascending `speakers.id`. The rendered pair puts the smaller number first. The user never types these numbers.
- **Line length, in tenths of a second.** English: `speech_tenths = words * 4`, which is `words / 2.5` seconds and is exact in tenths. Word count uses §9.6. Other supported languages: `speech_tenths = (syllables * 20 + 8) // 9`, which is `syllables / 4.5` seconds rounded up to the next tenth. Syllables use §9.6. Marathi and Bengali use this same rate; the UI labels it "assumed". `line_tenths = speech_tenths + 5`. A shot with lines needs `end_ms - start_ms >= (10 + sum(line_tenths)) * 100`: each line contributes speech plus 0.5 s, and the shot adds 1.0 s once. A shot with no lines uses `pacing`: `silent` needs at least 1500 ms and `action` needs at least 2500 ms.
- **Worked example.** Five English words give `speech_tenths = 20` (2.0 s), a line estimate of 2.5 s, and a shot minimum of 3.5 s.
- **`text_raw` normalisation.** Strip trailing whitespace. Replace a trailing `।` or `॥` with `.`. If the last character is not `.`, `?`, or `!`, append `.`. These are the only mutations. Any other difference inside `<d>` is PF-07.
- **Time format.** From integer milliseconds, `MM` and `SS` are zero-padded to 2 and `mmm` to 3. Instruction-line `S.SS` is `str(duration_s) + ".00"`.
- **PF-26.** Count whitespace-separated words in `detailed_description`. Warn below 350 or above 500. Do not warn when the clip has 3 or more dialogue lines, or when `sum(speech_tenths) / 10 > 0.4 * duration_s`.

### 9.6 Parser, matchers, and autofix

`validation/parser.py` is the only parser. Rules consume `ParsedPrompt`. They do not keep private copies of these patterns.

**Normalisation.** Reject a body that contains `\r` or U+FEFF. Newlines are `\n`. Trailing spaces on a line are a PF-01 error. The stored `body` has no trailing newline.

**Mode recognition.**

- I2VA, FL2VA, and L2VA: the body starts with the exact instruction line from Appendix A.2 for that mode and those `N` and `S.SS` values, then `\n\n`. The em dash in the FL2VA and L2VA lines is U+2014. A hyphen-minus or en dash does not match.
- REF2VA: the first line is exactly `subject_definitions:`.
- T2VA: the first line starts with `integrated_multimodal_description: ` (one space after the colon) and there is no instruction line.

**REF2VA sections.** Header lines are exactly `subject_definitions:`, `summary:`, `retention_analysis:`, `detailed_description:`, `overall_soundscape:`, and `non_diegetic_music:`, in that order, with nothing after the colon. Exactly one empty line separates a section's last content line from the next header. `subject_definitions` and `retention_analysis` are one entry per line and contain no empty line. `summary` content is one line. `detailed_description` is one style line, then one line per shot. Each sound section is one line.

**T2VA and frame fields.** After the optional instruction block, three lines match `^(integrated_multimodal_description|overall_soundscape|non_diegetic_music): `. Content is the rest of that same line. Exactly one empty line separates the fields. The description contains `[Shot 1]` and no raw line break.

**Shots.** Find `\[Shot (\d+)\]` in order. Numbers are `1..n` with no gaps. Shot 1 is not followed by ` At `. Every later shot matches `\[Shot N\] At \d{2}:\d{2}\.\d{3}, the camera cuts to `.

**Camera phrases.** In each shot span, and in the REF2VA style line, scan left to right. At each character, try the patterns below from longest to shortest and consume the first hit. Two hits in one shot is a PF-04 error. A hit in the REF2VA style line is a PF-04 error.

| Pattern |
|---|
| `The camera holds a static shot` |
| `The camera pushes in` |
| `The camera pulls out` |
| `The camera zooms in` |
| `The camera zooms out` |
| `The camera pans left` |
| `The camera pans right` |
| `The camera tilts up` |
| `The camera tilts down` |
| `The camera trucks left` |
| `The camera trucks right` |
| `The camera pedestals up` |
| `The camera pedestals down` |
| `The camera arcs around <Subject \d+>` |
| `The camera tracks <Subject \d+>` |
| `The camera holds <Subject \d+>'s point of view` |
| `The camera shakes slightly` |
| `The camera shakes strongly` |
| `The camera rolls clockwise` |
| `The camera rolls counterclockwise` |

Non-REF arc, tracking, and POV use `The camera arcs around `, `The camera tracks `, and `The camera holds [^.]{1,60}?'s point of view`. The static phrase is tried before the POV pattern, so `The camera holds a static shot` is one static move. These extra clauses are not moves: `from the front`, `from behind`, `from the side`, `moving backward`, `at a steady distance`, `smoothly`.

**Landing.** A required move needs one of these substrings later in the same shot: ` toward `, ` revealing `, ` onto `, ` as `. Static, POV, and shake may include a landing and do not fail when it is missing (warning only). Any of `with small amplitude`, `with large amplitude`, `at slow speed`, or `at fast speed` on Static, POV, or shake is an error. Any other `amplitude` or `speed` phrase is an error on every move.

**Face heuristic (PF-05, overridable).** Exemption, lens, and expression checks use the shot text with `<d>…</d>` spans removed. Mouth-closure checks use the original shot text. A shot is exempt when the stripped text contains `from behind`, `faces not visible`, `face is not visible`, `no readable face`, `extreme wide shot`, or `silhouette`. A POV shot is exempt only when it also contains `face is not visible` or `faces not visible`; otherwise it fails. A non-exempt shot whose original text contains `</d>`, or whose stripped text contains `close-up`, `medium close-up`, or `medium shot`, must contain `front-facing` or `three-quarter`, and at least one of `eye`, `eyes`, `brow`, `brows`, `lip`, `lips`, `mouth`, `jaw`, `breath`, `hand`, `hands`, `shoulder`, `shoulders`, `gaze`, `tear`, `smile`. It fails on a case-insensitive hit of `24mm`, `wide-angle`, `fisheye`, `ultra-wide`, `GoPro`, or `action cam`. It fails when `front-facing` occurs more than twice or when the shot contains `three faces`, `four faces`, or `many faces`. After a non-voiceover `</d>`, the next 80 characters of the original text must contain `lips`, unless `<cutoff>` follows that `</d>`. A voiceover sentence must contain `lips remain completely closed`.

**Sound lexicon (PF-34).** After removing the exact house sentence, `<d>…</d>` spans, and straight double-quoted spans, a case-insensitive whole-word hit of any of these tokens is a violation under `dialogue_only` or `silence`: `footstep`, `footsteps`, `hum`, `hums`, `buzz`, `buzzes`, `clang`, `clangs`, `creak`, `creaks`, `echo`, `echoes`, `thunder`, `drone`, `drones`, `jingle`, `whistle`, `birdsong`, `clack`, `splash`, `splashes`, `rustle`, `thud`, `bang`, `siren`, `sirens`, `rain`, `rains`. `music` is not in this list, because the house sentence uses it.

**Mood words (PF-08b).** Case-insensitive whole words, music field only. Errors: `tense`, `sad`. Warnings: `angry`, `anxious`, `calm`, `dark`, `dreamy`, `emotional`, `epic`, `fearful`, `happy`, `hopeful`, `joyful`, `melancholic`, `menacing`, `mysterious`, `ominous`, `peaceful`, `romantic`, `scary`, `suspenseful`, `tragic`, `uplifting`.

**Sentence count.** Split the field on `[.!?]` that is followed by whitespace or end, except a dot after `Mr`, `Mrs`, `Ms`, `Dr`, `St`, `vs`, or `etc`, and except a dot between digits. The count of pieces that contain a letter is the sentence count.

**Emotion filler (PF-33).** Case-insensitive whole words `4k`, `masterpiece`, `high quality`, `epic`, `dynamic camera`, `cool VFX`, `nervous`, `angry`, `sad`, `happy`, `scared`, `afraid`, `emotional`, `upset`, `excited`, `anxious`. For an emotion word only (the list from `nervous` through `anxious`), suppress the warning when the same shot also contains one of the physical tokens listed under the face heuristic. Tag hits are never suppressed.

**Syllables (§9.5).** Use the script block and virama for the line's language: Devanagari U+0900–U+097F virama U+094D (Hindi, Marathi); Bengali U+0980–U+09FF virama U+09CD; Tamil U+0B80–U+0BFF virama U+0BCD; Telugu U+0C00–U+0C7F virama U+0C4D; Kannada U+0C80–U+0CFF virama U+0CCD; Malayalam U+0D00–U+0D7F virama U+0D4D. Walk the code points. Count a character when its category is `Lo`, it lies in the script block, and the previous code point is not that virama.

**English words.** Count regex matches of `[A-Za-z0-9]+(?:'[A-Za-z]+)?` in `text_raw`.

**Autofix, in order, before any fixer call.** Each step re-parses.

1. In a shot header, replace `At (\d{2}):(\d{2}):(\d{3})` with `At \1:\2.\3`.
2. Replace `the shot cuts to` with `the camera cuts to` when it follows a legal timestamp.
3. Replace a lowercase official phrase with the capitalised phrase from the table (`the camera pushes in` → `The camera pushes in`).
4. Replace `:` immediately before `<d>` with `,`.
5. Under `dialogue_only`, set both sound fields to `N/A` (both single-line `overall_soundscape: N/A` and multiline REF2VA `overall_soundscape:\nN/A`) and insert the house sentence at the §7.6 position when it is absent. Under `silence`, set both sound fields to `N/A` and delete the house sentence when present. Under `custom`, delete the house sentence when it is present.

Autofix does not invent missing sections, shots, or labels.

---

## 10. Export Module

### 10.1 Export collision and revision policy

- File name `clip-<NN>-<D>s.txt`; `NN` zero-padded to ≥ 2 digits; `D` = stored `duration_s` (never parsed back from the name).
- **Collision is decided on integer `NN` alone**, regardless of `D`: if any existing file matches `clip-(\d+)-.*` with integer value equal to `int(NN)` (e.g. `clip-1-8s.txt` and `clip-01-8s.txt` collide), the collision policy applies. This prevents duplicate clip numbering across padded and unpadded variants or different durations.
- `NN` suggestion: scan `clip-(\d+)-\d+s\.txt` in the export directory, take max + 1; user may override.
- Policies: `auto_increment` (next unused `NN`, applied consistently to the prompt file, PLATES file, snapshot name and DB record) or `prompt_override` (`409 Conflict` listing colliding files unless the request has `"overwrite": true`). Never a silent overwrite.
- **Atomic writes.** Write the bytes to a temporary file in the export directory. When the request does not set `"overwrite": true`, `os.link` the temp onto the final path and then delete the temp. `os.link` fails if the name exists, so a race cannot overwrite. When `"overwrite": true`, `os.replace` the temp onto the final path. If `os.link` fails because the two paths are on different filesystems, write the final file with `open(path, "x")` instead. Delete the temp file on every exit path. The file is UTF-8, uses `\n`, and has no BOM. `char_count` is the number of Unicode code points in `body`. `body` has no trailing newline. The file bytes are `body` plus one `\n`. That final newline is outside the 7000 limit.
- **Order:** (1) re-run preflight on the selected prompt; refuse if blocked or stale; (2) JSON snapshot to `data/backups/clip-<id>-<ts>.json` (full clip state, references, subjects, shots, lines, retention, prompt template + body, overrides, target path); (3) write prompt file; (4) write PLATES (REF2VA); (5) update DB (`prompts.exported_filename`, `exported_at`, `clips.status = 'exported'`). If step 3/4 fails, remove files written in this export, leave DB unchanged, return an error.
- Snapshots pruned to the **last 5 per clip** (Q-11) after a successful export.

### 10.2 House pipeline export artifacts

1. **Prompt file** `clip-<NN>-<D>s.txt` — plain UTF-8 raw prompt: no fences, no metadata.
2. **PLATES** (REF2VA only) — `clip-<NN>-PLATES.txt`, one line per reference token in `position` order: `<Label>: <filename-or-MISSING> — <role>: <caption>`. The dash is U+2014. An empty filename is `MISSING`. The role list joins the picture's roles, in this order, with `, `: identity anchor, outfit, prop, location, composition anchor, framing reference, first frame, keyframe, last frame. A reference with no role uses `unassigned`. This is the v1 export convention. The app does not read or write a scene-folder `PLATES.txt`, and does not produce an aggregate `PLATES.txt`.
3. **Clipboard copy** — exactly the file's text (browser Clipboard API; `localhost` is a secure context; fallback to a selectable textarea if denied).
4. **Metadata block** (UI only, never in the file): mode, H3 video model, duration, resolution, ratio, attach order, voice IDs.
5. **Variations** — the draft is variation one; "Safer framing" may add one more. The panel shows both; export uses the selected one. A third is refused.

---

## 11. Documentation Plan

### 11.1 README.md (setup)

1. What the app is; the five modes.
2. Prerequisites: Python ≥ 3.10, Ollama running locally, a pulled drafter (`ollama pull qwen2.5:7b-instruct`); venv note.
3. Install: venv, `pip install -r requirements.txt` (pinned), first run; `data/` creation, migration check.
4. Configuration: Ollama endpoint, drafter prefetch, H3 video model, data dirs, port, env overrides.
5. Quick start: a T2VA clip in 4 steps.
6. Where things live: application modules, `data/`, `exports/`, `backups/`, and `logs/`.
7. Testing: `pytest`; what the suites cover (§14), including conformance to this specification.
8. Troubleshooting (Ollama unreachable, no model, timeouts, slow first call, 409 busy, 412 precondition, stale prompt, export collision).

### 11.2 USER_GUIDE.md

**Novice:** first launch and Settings; T2VA from a one-sentence seed (+ manual draft); I2VA; FL2VA and L2VA; reading the preflight panel (green / red-fixable / red-input-required / yellow warning / overridable); exporting and collisions.

**Advanced:** REF2VA walkthrough (task-type prefixes, retention markers, tables); voice library, camera vocabulary, and face-safety rules from Appendix A; house audio rule, custom sound, silence; dialogue conventions; pipeline conventions (PLATES, clip numbering, ComfyUI handoff); troubleshooting mapped to PF IDs; local-model tuning (`temperature`, `num_ctx`, seed, JSON schema mode, why stages and placeholders exist); backups and recovery.

---

## 12. Pre-Implementation Gates & Resolved Design Decisions

### 12.1 Gate status (all resolved)

1. Malformed-output repair contract → §5.5, §8.0, §8.
2. Validation rule registry → §1.5, §9.
3. REF2VA structured serialization → §6.1, §6.1.1.
4. Export collision and revision policy → §10.1.
5. Self-contained normative contract → Header, §1.4, §5.7, Appendix A.
6. **(v1.3)** Prompt-writing stage for non-REF modes → §8.1b.
7. **(v1.3)** Verbatim-text preservation mechanism → §8.0.
8. **(v1.3)** Data-integrity of references/anchors/staleness → §6.1, §5.7, PF-30.

### 12.2 Resolved decisions (`Q-01`–`Q-16`)

| # | Question | Decision |
|---|---|---|
| Q-01 | Sub-tab alias naming | `FL2VA (flf2va)`, `L2VA (lf2va)` via registry |
| Q-02 | Back-end | FastAPI + Uvicorn + httpx + stdlib sqlite3, venv |
| Q-03 | Front-end | Vanilla JS ES modules, Nord CSS variables, no build step |
| Q-04 | Assembler | Deterministic renderer only; LLM assembler removed in v1.3 |
| Q-05 | Export directory | Single configured directory (`data/exports/`); scene-folder mirroring v2 |
| Q-06 | Tokens vs uploads | Tokens + typed filenames, dimensions, durations; no file access |
| Q-07 | Clip numbering | Auto-suggest `NN`, manual override, collision on `NN` alone |
| Q-08 | Local drafter | Tuned for `qwen2.5:7b-instruct`-class; temperature 0.2, `num_ctx` 8192, timeout 120 s |
| Q-09 | Non-English seed/action | Any language accepted; prose English; dialogue/on-screen text verbatim via placeholders |
| Q-10 | Concurrency | One generation at a time (lock, `409`), streamed progress, cancel |
| Q-11 | History | Last 5 snapshots per clip |
| Q-12 | REF2VA `summary` visibility | Review card (`prompts.summary_text`) and inside the prompt |
| Q-13 | Manual drafting | `manual_draft` + `manual_template`; renderer + preflight only |
| Q-14 | Heuristic false positives | Explicit logged override for heuristic rules only (§9.4) |
| Q-15 | Fixer scope | Template-only edits, placeholder-integrity guard, deterministic autofix first |
| Q-16 | PLATES aggregate | Per-clip `clip-<NN>-PLATES.txt` only in v1; aggregate `PLATES.txt` deferred (N-06) |
| Q-17 | Where voice lives | Per speaker (`speakers` table), not per line (F-03) |
| Q-18 | Task types | User-confirmed; only guidance/anchor/timbre types auto-defaulted (F-07) |
| Q-19 | Romanised dialogue | Blocked with input-required error; optional confirm-both helper (F-11) |

---

## 13. Acceptance Criteria

### 13.1 Mode behaviour

| # | Criterion |
|---|---|
| A-01 | **T2VA:** one-sentence seed → exactly `integrated_multimodal_description`, `overall_soundscape`, `non_diegetic_music`; no instruction line; `plain` opens with an allowed pair (default `Live-action, cinematic`); named style opens with the exact prefix in Appendix A.10; concrete ratio; dialogue-only sentence verbatim. Passes PF-01…PF-13, PF-28, PF-29. |
| A-02 | **I2VA:** starts with `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` then the three fields; ratio `adaptive`. |
| A-03 | **FL2VA:** starts with `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.` — no angle/square brackets; `S.SS` two decimals; `N` equals the final shot index of the rendered prompt. |
| A-04 | **L2VA:** starts with `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.` — brackets kept. |
| A-05 | **REF2VA:** References + Subjects (0, 1, or multiple linked pictures) + Shots on a flat single canvas → six sections in exact order. Subject lines follow stock deterministic formulas (`his`/`her`/`its`) without free picture descriptions. `summary` has one bracketed prefix (types joined by ` + `, none repeated) and no new labels. `retention_analysis` has valid markers, no `(Sx)`. Style sentence starts `The target video is …` before `[Shot 1]`. Cuts use `the camera cuts to`. |
| A-06 | Instruction lines are app-generated; the LLM never composes them. |
| A-07 | At most two variations (draft + one safer framing) per generation. |

### 13.2 Validation and limits

| # | Criterion |
|---|---|
| A-08 | A deliberately broken prompt (`00:03:000`, timestamp ≥ duration, T2VA `adaptive`, sound in a dialogue-only clip, `(S1)` in `retention_analysis`, a translated `<d>` line, a bare `F3`) produces blocking PF errors with quoted corrections. |
| A-09 | The fixer resolves `fixable: true` violations within max retries; `fixable: false` or unresolved errors block export. A fixer output that alters placeholders is rejected. |
| A-10 | The counter blocks/annotates a `body` of more than 7000 Unicode code points. The export newline is not counted. |
| A-11 | REF2VA counters refuse a 10th image (> 9), a 4th video or audio (> 3), a 13th file (> 12), a duration outside 2–15 s or total > 15 s per type. Image dimensions are optional metadata; if entered, values outside 256–5760 px or ratio outside 0.4–2.5 yield non-blocking preflight warnings, not export blocks. |
| A-12 | Cut times strictly increasing, `MM:SS.mmm`, below duration. Shot counts respect the table. An 8-second one-shot FL2VA landing on Picture 2 exports successfully. |

### 13.3 Ollama integration

| # | Criterion |
|---|---|
| A-13 | On startup and "Refresh models", `GET /api/tags` populates the dropdown. |
| A-14 | `POST /api/show` info (family, parameter size, quantization, context length) is displayed. |
| A-15 | The selected model is persisted and used by every LLM stage; JSON stages send a JSON Schema (or `"json"` fallback); `options` include `temperature`, `num_ctx`, `seed`, `num_predict`. |
| A-16 | Unreachable Ollama or empty list shows an explicit error with an `ollama pull …` hint; no silent fallback, no cloud API. |

### 13.4 Export and data

| # | Criterion |
|---|---|
| A-17 | Export writes `clip-<NN>-<D>s.txt` without silently overwriting; collision is detected by `NN` alone; `D` is the stored duration. |
| A-18 | REF2VA export writes `clip-<NN>-PLATES.txt` in attach order with `MISSING` markers where needed. |
| A-19 | Clipboard copy contains the raw prompt only. |
| A-20 | All data persists in `data/h3studio.db` (FKs on, WAL) or designated JSON; a snapshot is written before each export; last 5 per clip retained; export is atomic (failed write leaves no partial files and no DB change). |
| A-21 | Bundled vocabularies load from read-only JSON and match the normative values in Appendix A; `/api/health` reports the application’s specification version. No external rule tree or checksum is required. |

### 13.5 UX and docs

| # | Criterion |
|---|---|
| A-22 | Nord Dark default; Coloured and Light switchable without reload; monospace `nord6` prompt text with `nord8` accents. |
| A-23 | Two top-level tabs and five sub-tabs render from the registry. |
| A-24 | REF2VA single-canvas layout; all cards visible simultaneously without wizard locks or gating; `wizard_step` persists with default 1 for database backward compatibility. |
| A-25 | README covers setup, venv, Ollama; USER_GUIDE covers novice walkthroughs per mode and the §11.2 advanced sections. |
| A-26 | `MiniMax-H3` rejects duration 3, 16, and `480P`; `MiniMax-H3-Max` rejects duration 4 and `2K`. Switching model clamps/clears and says so. The drafter name does not affect these limits. |
| A-27 | A Kannada line appears inside `<d>[Kannada] …</d>` byte-identical to `text_raw` (apart from §9.5 terminal-punctuation normalisation); no native-script text was ever sent to the LLM; surrounding fields are English. |
| A-28 | "Safer framing" produces at most one extra prompt, keeps placeholders/timestamps, and is the export source only when selected. A second click returns `409`. |

### 13.6 Robustness (new in v1.3)

| # | Criterion |
|---|---|
| A-29 | Stage 0 failure (e.g. `2K` on H3-Max, missing image width) makes **zero** Ollama calls and highlights the field. |
| A-30 | Concurrent `/generate`, `/fix` or `/variations` returns `409`; the lock is released on error, cancel, and client disconnect; clips left `generating` after a crash are reset on startup. |
| A-31 | Editing any generation-relevant input after generation marks the prompt stale (PF-30) and disables export; deleting a reference shows the re-numbering diff and does not orphan links (FK + `ON DELETE CASCADE`/`SET NULL` behaviour tested). |
| A-32 | Worst-case LLM call counts of §5.5 are never exceeded (tested with a failing fake Ollama). |
| A-33 | A truncated (`done_reason: "length"`), empty, non-JSON or schema-invalid response triggers exactly one retry, then a stage error with partial state preserved. |
| A-34 | Heuristic false positives can be overridden with a logged note; structural rules cannot; an override is dropped if the prompt body changes. |
| A-35 | Requests with a foreign `Host`/`Origin` are rejected; the server binds only to loopback. |
| A-36 | Two browser tabs editing the same clip: the second write returns `412` and the UI prompts a reload. |
| A-37 | The same inputs, drafter, and fixed seed build the same Ollama payload (`seed`, `temperature`, `num_ctx`, and prompt text). The test uses a fake Ollama and compares payloads. |
| A-38 | REF2VA output uses stand-alone section headers, one entry per line and `[Shot N]` per line; T2VA/frame output uses single-line `field: content` (PF-01, §7.6). |
| A-39 | Subject lines render correctly for a uniformed person with appositive (`…, a convict, with her face, hair, build, and complete outfit …`), a person with `uniform`, and a location (`…, including its walls, floor, and layout exactly as shown.`). |
| A-40 | One speaker keeps one voice phrase/accent across all lines; a voiceover uses the speaker's pronoun (`her lips remain completely closed`). |
| A-41 | A Kannada line typed in Latin letters is rejected at Stage 0 with zero Ollama calls (PF-31); a code-mixed line with English words inside Kannada script passes. |
| A-42 | PLATES lists references in Reference Manager row order, not grouped by type; reordering renumbers per-kind labels and marks prompts stale. |
| A-43 | `video editing` cannot be selected without a video reference; its summary opens `The target video is an edited version of <Video K>.` where K is the lowest video ordinal; auto-defaults never include editing, continuation, or reuse. |
| A-44 | T2VA rejects `<Picture>`, `<Subject>`, `<Audio>`, and `<Video>` tokens. A Static shot without a landing yields a warning. A Push without one yields an error. |
| A-45 | A picture linked as both `location` and `composition_anchor` renders two definition lines. Renumbering updates labels from ordinals. A speaker's audio link stores `audio_reference_id`, so the rendered `<Audio N>` follows the row's current ordinal. |
| A-46 | A line with `speaker_id_2` renders one `(S1,S2)` tag and one `<d>` span. A cross-cut line puts `<scenetrans>` immediately before `<d>` in the source shot; in the destination shot ($N > 1$), `<scenetrans> The audio continues seamlessly across the cut.` is placed immediately after the cut header. |
| A-47 | The Ollama request for a line contains the gloss or the words `meaning unknown`, and does not contain `text_raw`. |
| A-48 | `/api/health` returns `specification_version` equal to `0.3`. `bind` is `127.0.0.1:` plus the port the process bound. Startup rejects `H3_HOST` other than `127.0.0.1`. Runtime paths match §17.2. |
| A-49 | The listen port is `H3_PORT` when that variable is set, otherwise settings `listen_port`, otherwise `9013`. Values outside 1–65535 are rejected. A saved port is used on the next start and does not rebind the running process. |

---

## 14. Test Plan

Run with `pytest`; no network and no real Ollama required for the default suite.

1. **Specification conformance:** all bundled resources, registry entries, and prompt templates match the normative values and exact strings in §§6–10 and Appendix A; no external source tree, manifest, or network access is used.
2. **Rule unit tests:** every PF rule, including PF-34 and PF-35 and the warning subcases of PF-02, PF-04, PF-08b, and PF-12, has at least one passing and one failing fixture in `tests/fixtures/`. Boundaries include duration 4/5/15/3/16, the 9th and 10th image, the 12th and 13th file, audio totals 15000 and 15001 ms, ratio 0.4 and 2.5, image sides 256/5760/255/5761, and the five-English-word shot minimum of 3.5 s.
3. **Golden render tests:** instruction lines for I2VA/FL2VA/L2VA byte-exact (including `—`, no brackets for FL2VA, `8.00`); house audio sentence; `MM:SS.mmm` formatter (property-based over 0–15000 ms); `(Sx)` ordering; PLATES lines.
4. **Placeholder tests:** round-trip with Kannada/Hindi text; integrity failures (duplicate, missing, unknown, misplaced); terminal punctuation normalisation.
5. **Stage contract tests** with an `httpx.MockTransport` fake Ollama: valid JSON, invalid JSON, empty, truncated, schema-invalid, slow (timeout); verify one retry, seed/temperature bump, payload shape (`format`, `options`), and worst-case call counts.
6. **Fixer tests:** deterministic autofix first; LLM fixer rejected when placeholders change; retry cap; non-fixable short-circuit.
7. **API tests** (FastAPI `TestClient`): CRUD cascades, `If-Match`/`412`, lock/`409`, stale marking, variations `409`, Host/Origin rejection, export collision matrix (same `NN` different `D`, auto_increment, overwrite), atomicity (simulated write failure), snapshot pruning.
8. **DB tests:** PRAGMAs applied, migrations forward-only with pre-migration backup, newer-schema abort, FK behaviours.
9. **Acceptance mapping:** one test (or a documented manual step for UI-only criteria A-22–A-25) per A-xx; a table in `tests/ACCEPTANCE.md` maps each ID to its test.
10. **Smoke (optional, marked `live`):** against a real Ollama with `qwen2.5:7b-instruct`, run one clip per mode and require preflight pass within the retry budget; records timings.

---

## 15. Implementation Milestones

Each milestone is independently runnable and testable. Approval is recorded below; a milestone may start.

| M | Scope | Exit criteria |
|---|---|---|
| M0 | Skeleton, config, DB + migrations, specification-version health endpoint, security middleware | Tests 1, 8 pass; `/api/health` green |
| M1 | Parser, estimators, rule registry, all PF rules, normalized violations, overrides | Tests 2, 3 (partial) pass |
| M2 | Placeholders + renderer + exporter | Tests 3, 4, 7 (export) pass |
| M3 | Ollama connector, stage runner, retry, lock, streaming | Test 5 passes; A-13…A-16, A-30, A-32, A-33 |
| M4 | T2VA end-to-end (UI + pipeline + fixer) | A-01, A-08…A-10 |
| M5 | I2VA/FL2VA/L2VA | A-02…A-04, A-12 |
| M6 | REF2VA (manager, editor, shots, Step 4, retention) | A-05, A-11, A-24 |
| M7 | Settings, themes, voice library, variations, docs, live smoke tests | A-22, A-23, A-25…A-28, A-31, A-34…A-37 |

---

## 16. Assumptions resolved as product decisions

These items were previously described as needing external verification. They are now explicit v1 decisions and do not require external material:

| ID | Product decision |
|---|---|
| D-01 | Outfit-only and prop subjects use the deterministic formulas in Appendix A.9. |
| D-02 | PLATES output uses the exact per-line format in §10.2. It is an H3 Prompt Studio export convention, not a MiniMax API requirement. |
| D-03 | Simultaneous speakers are rendered `(S1,S2)` in speaker-ID order. A cross-cut line puts `<scenetrans>` immediately before `<d>` in the source shot and prefixes the destination shot once with `<scenetrans> The audio continues seamlessly across the cut. `. Render `<cutoff>` immediately after `</d>` for a line cut off by video end. Voiceover closure text follows any `<cutoff>`. |
| D-04 | Default retention markers are the deterministic mappings in §8.6 / Appendix A.9. The user can change each marker before generation. |
| D-05 | The dialogue-only sentence position is fixed in §7.6 and is inserted once by the renderer. |
| D-06 | No scene-folder integration, project-specific prompt convention, or aggregate PLATES file is part of v1. Clip numbering and export layout are fully defined in §10. |
| D-07 | When a format detail has multiple plausible forms, this document's exact template and validator rule decide the v1 behavior. Do not fetch an external document or silently infer a different rule. |

| D-08 | Shot minima use the integer tenths in §9.5. Several lines in one shot add 0.5 s each and add the extra 1.0 s once. |
| D-09 | The renderer repeats the full voice phrase on every line. |
| D-10 | Task types are stored in the §6.4 order. `video editing` opens the summary with `The target video is an edited version of <Video K>.`, where K is the lowest video ordinal. `video continuation` has no second fixed sentence; the bracket prefix is the marker. |
| D-11 | A named-style prefix stops before the shot size. The words `a medium close-up frames` are an illustration, not required text. |
| D-12 | `{{Lk}}` expands to the full §8.0 speech sentence. The model does not write voice or dialogue text. |
| D-13 | The 7000 limit counts Unicode code points of `body` and excludes the single export newline. The frame-mode dash is U+2014. |

No unresolved external verification item blocks implementation.

---

## 17. Local paths on this machine

`<repo>` is `/home/wizdroid/Applications/h3-mechanic`. A relative path in this document is under that directory unless this section gives a different absolute path. The name `h3-prompt-studio/` in the §5.2 diagram is the application name. It is not a directory. The files in that diagram are created under `<repo>`.

The H3 rules stay in the sections and Appendix A. §17.2 paths are required for the process. §17.3 paths are the reference set used to certify this revision. The process does not open, fetch, or checksum a §17.3 file. If a reference file and this specification disagree, this specification wins (D-07).

### 17.1 Repository root

| Use | Path |
|---|---|
| Repository root (`<repo>`) | `/home/wizdroid/Applications/h3-mechanic` |
| This specification | `/home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.3.md` |

### 17.2 Runtime paths (required)

First run creates `data/`, `data/exports/`, `data/backups/`, and `data/logs/`. The export directory setting may later name another absolute writable directory. The default is the path in this table.

| Use | Path |
|---|---|
| SQLite database | `/home/wizdroid/Applications/h3-mechanic/data/h3studio.db` |
| Export directory | `/home/wizdroid/Applications/h3-mechanic/data/exports` |
| Clip snapshots | `/home/wizdroid/Applications/h3-mechanic/data/backups/clip-<id>-<ts>.json` |
| Pre-migration database copy | `/home/wizdroid/Applications/h3-mechanic/data/backups/h3studio-pre-migration-<ts>.db` |
| Log | `/home/wizdroid/Applications/h3-mechanic/data/logs/app.log` |
| Application package | `/home/wizdroid/Applications/h3-mechanic/app/` |
| Migrations | `/home/wizdroid/Applications/h3-mechanic/app/storage/migrations/` |
| Derived vocabularies | `/home/wizdroid/Applications/h3-mechanic/app/resources/` |
| Web UI | `/home/wizdroid/Applications/h3-mechanic/app/web/` |
| Tests | `/home/wizdroid/Applications/h3-mechanic/tests/` |
| Acceptance map | `/home/wizdroid/Applications/h3-mechanic/tests/ACCEPTANCE.md` |
| Requirements file | `/home/wizdroid/Applications/h3-mechanic/requirements.txt` |
| Process URL | `http://127.0.0.1:<listen_port>` (default `http://127.0.0.1:9013`) |
| Ollama endpoint | `http://127.0.0.1:11434` |

The listen port is resolved by §5.7. `H3_HOST` is accepted only when its value is `127.0.0.1`. Any other value aborts startup.

### 17.3 Reference paths (not loaded at runtime)

Cheatsheets, one directory, `/home/wizdroid/Applications/h3-mechanic/cheatsheets/`:

| File | Path |
|---|---|
| Index | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/README.md` |
| Modes and hard limits | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/01-modes-and-hard-limits.md` |
| Shared grammar | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/02-shared-grammar.md` |
| Camera motions | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/03-camera-motions.md` |
| Framing and timing | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/04-framing-and-timing.md` |
| Voice library | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/05-voice-library.md` |
| Expressions and delivery | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/06-expressions-and-delivery.md` |
| Languages and on-screen text | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/07-languages-and-on-screen-text.md` |
| T2VA | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/08-t2va.md` |
| I2VA, FL2VA, L2VA | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/09-i2va-fl2va-l2va.md` |
| REF2VA | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/10-ref2va.md` |
| 1980s Bollywood style | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/11-style-80s-bollywood.md` |
| Cinematic modern style | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/12-style-cinematic-modern.md` |
| Modern series style | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/13-style-modern-series.md` |
| Noir thriller style | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/14-style-noir-thriller.md` |
| Troubleshooting | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/15-troubleshooting.md` |
| Preflight checklist | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/16-preflight-checklist.md` |
| Source workbook | `/home/wizdroid/Applications/h3-mechanic/cheatsheets/minimax-h3-cheatsheet-categorized.xlsx` |

Prompt-writing skill, `/home/wizdroid/.grok/skills/h3-prompt-writing/`:

| File | Path |
|---|---|
| Skill | `/home/wizdroid/.grok/skills/h3-prompt-writing/SKILL.md` |
| Modes and limits | `/home/wizdroid/.grok/skills/h3-prompt-writing/references/01-modes-and-limits.md` |
| Shared grammar | `/home/wizdroid/.grok/skills/h3-prompt-writing/references/02-shared-grammar.md` |
| T2VA | `/home/wizdroid/.grok/skills/h3-prompt-writing/references/03-t2va.md` |
| I2VA, FL2VA, L2VA | `/home/wizdroid/.grok/skills/h3-prompt-writing/references/04-i2va-fl2va-l2va.md` |
| REF2VA | `/home/wizdroid/.grok/skills/h3-prompt-writing/references/05-ref2va.md` |
| Singularity patterns | `/home/wizdroid/.grok/skills/h3-prompt-writing/references/06-singularity-patterns.md` |
| Preflight and output | `/home/wizdroid/.grok/skills/h3-prompt-writing/references/07-preflight-and-output.md` |

Earlier specifications, kept as history:

| Revision | Path |
|---|---|
| 1.1 | `/home/wizdroid/Applications/h3-mechanic/docs/specifications/specification.md` |
| 1.2 | `/home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-1.2.md` |
| 1.4 | `/home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-1.4.md` |
| 1.5 (approved) | `/home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-1.5.md` |
| 1.6 (certified) | `/home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-1.6.md` |
| 0.1 | `/home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.1.md` |
| 0.2 | `/home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.2.md` |

The repository README at `/home/wizdroid/Applications/h3-mechanic/README.md` describes an earlier layout. It is not the v0.1 application tree.

---

## Appendix A. Complete H3 format, vocabulary, and defaults

This appendix is normative. The application may store the values in code or JSON, but it must implement the values below without an external lookup. Exact punctuation, capitalization, labels, and phrases in quoted templates are significant.

### A.1 Mode selection and hard limits

| Input and intent | Mode | Required ratio |
|---|---|---|
| Text only | T2VA | Concrete ratio |
| One image is the exact opening frame | I2VA | `adaptive` |
| Two images are the exact first and last frames | FL2VA | `adaptive` |
| One image is the exact final frame | L2VA | `adaptive` |
| Character, location, prop, motion, or voice references are not literal frames | REF2VA | `adaptive` by default; concrete ratio allowed |

Default to I2VA when the image is the exact opening frame. Use REF2VA instead when a required face is hidden, turned away, or out of frame; an unlisted person appears; the camera reveals a new side that must match; or an audio/motion reference is needed. Never mix reference roles (`reference_image`, `reference_video`, `reference_audio`) with first/last-frame roles. I2VA cannot take extra character images: every person who must match exactly must already appear in the first frame.

| H3 video model | Allowed duration | Allowed resolution |
|---|---:|---|
| `MiniMax-H3` | Integer 4–15 seconds | `768P`, `2K` |
| `MiniMax-H3-Max` | Integer 5–15 seconds | `480P`, `768P` |

Concrete ratios are exactly `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, and `9:16`; `adaptive` is invalid for T2VA. REF2VA permits either `adaptive` or a concrete ratio. H3 limits are independent of Ollama drafter model and settings.

REF2VA budgets: at most 9 images, 3 videos, 3 audio clips, and 12 files total. Every audio/video clip is 2–15 seconds; total duration is at most 15 seconds for each media type independently. Every image has width and height in the inclusive range 256–5760 px, and width/height ratio in [0.4, 2.5]. The same image constraints apply to I2VA/FL2VA/L2VA frame images. The rendered prompt `body` is at most 7000 Unicode code points. The export newline is outside that count.

### A.2 Exact prompt structure

All prompt prose is English except native-script dialogue inside `<d>` and verbatim text visibly present in the scene inside double quotes. No markdown fences or bullets are part of the exported prompt.

**T2VA** has exactly these three fields, each on one line, separated by one blank line. The first field contains one continuous paragraph; `[Shot 1]` is untimed:

```text
integrated_multimodal_description: [Shot 1] <style opening and shot prose; later shots are inline>

overall_soundscape: <N/A or 1–4 sentences>

non_diegetic_music: <N/A or 1–3 sentences>
```

**I2VA, FL2VA, and L2VA** start with their exact instruction line, then one blank line, then the same three fields and layout as T2VA:

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
```

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

The three exact instruction lines above respectively belong to I2VA, FL2VA, and L2VA. For FL2VA, there are no angle or square brackets around picture/shot labels in the instruction line. `N` is the actual final shot index. `S.SS` is the stored clip duration with exactly two decimal places. The app writes these lines; neither the LLM nor the user authors them.

**REF2VA** has exactly these six sections in order. A section header is alone on a line; content follows on subsequent lines, with one blank line between sections. Subject definitions and retention entries are one per line; each shot begins on its own line:

```text
subject_definitions:
<one definition per line>

summary:
[task type] <one paragraph>

retention_analysis:
<one entry per line>

detailed_description:
The target video is <style opening>.
[Shot 1] <shot prose>
[Shot 2] At MM:SS.mmm, the camera cuts to <shot prose>

overall_soundscape:
<N/A or 1–4 sentences>

non_diegetic_music:
<N/A or 1–3 sentences>
```

REF2VA style sentence(s) precede `[Shot 1]` and begin `The target video is`. The `summary` has exactly one bracketed prefix; multiple task types are joined by ` + ` inside the same pair of brackets. Each summary is one paragraph and may use only labels defined in `subject_definitions`.

### A.3 Shared dialogue, sound, and timing grammar

- Shot 1 is `[Shot 1]` with no timestamp. Every later shot is `[Shot N] At MM:SS.mmm, the camera cuts to …`; timestamps strictly increase and are less than the clip duration. The timestamp form is `MM:SS.mmm` (for example `00:03.000`, never `00:03:000`).
- Use one camera move per shot. A second move requires a new shot. Describe the move as a natural-language action; do not append tag lists.
- Speaker IDs `(S1)`, `(S2)`, etc. are assigned by first vocal event, persist across shots, and are never typed by the user. Simultaneous speakers are `(S1,S2)`, ordered by assigned ID.
- Put voice identity, accent, and delivery outside the dialogue tag. Use `<d>[Language] exact native-script words.</d>`. The text is verbatim except for the terminal punctuation normalization in §9.5. One `<d>` span has one dominant language; code-mixed English words may remain in Latin script within that span. Distinct full-language utterances use separate spans.
- For a cross-cut line, put `<scenetrans>` immediately before `<d>` in the source shot, and prefix the destination shot once with `<scenetrans> The audio continues seamlessly across the cut. `. For a video-end cutoff, put `<cutoff>` immediately after `</d>`. For voiceover, write `says in an off-screen voiceover`; the closure is the §8.0 sentence, including `while {his|her|its} lips remain completely closed`.
- A line that ends during the shot is followed by explicit mouth closure (`She closes her lips …`). A listening face is described with closed lips. Every readable face has one observable expression clause per shot; show physical evidence (eyes, brows, mouth, jaw, breath, hands, shoulders), not an emotion label alone.
- The default audio policy is dialogue-only: both sound fields are `N/A`; shot prose contains no sound descriptions. The renderer inserts, once, at the §7.6 position: `The audio contains only the spoken dialogue, with no background music, no ambience, and no sound effects.` This sentence is still required when no dialogue line exists.
- Under custom audio, soundscape is 1–4 sentences; music is 1–3 sentences or `N/A`. Music descriptions name instrumentation, tempo, and dynamics only; do not use mood words. Character-audible music belongs in shot prose. Total silence uses `N/A` for both sound fields.
- Durations use the integer formula in §9.5. English is 2.5 words/second (`speech_tenths = words * 4`). Kannada, Hindi, Tamil, Telugu, Malayalam, Marathi, and Bengali are 4.5 syllables/second, rounded up to the next tenth. Add 0.5 s per line and 1.0 s once per shot. Silent shots last at least 1.5 s. Action shots with no line last at least 2.5 s.

### A.4 Shot budgets, sizes, angles, and face safety

| Clip duration | Minimum | Maximum | Planner target |
|---|---:|---:|---|
| 4–6 s | 1 | 2 | 1 |
| 7–10 s | 2 | 3 | 2 |
| 11–15 s | 2 | 4 | 2 or 3 |

PF-03 is an error when the count is below the minimum or above the maximum. The planner target is the count the model is asked to aim for. A count inside the minimum and maximum is legal when it is not the target. FL2VA with `requested_shot_count = 1` may use one shot at every allowed duration. A longer FL2VA still respects the maximum. The last shot runs to the clip end.

| Abbrev. | Shot-size phrase | Readability |
|---|---|---|
| ECU | `an extreme close-up of her eyes` | Partial |
| CU | `a close-up of <Subject 1>'s face` | Best |
| MCU | `a medium close-up framing <Subject 1> from the chest up` | Best; default for dialogue |
| MS | `a medium shot framing both of them from the waist up` | Good; maximum two readable faces |
| MWS | `a medium-wide shot framing them from the knees up` | Fair |
| WS | `a wide shot` | Poor; rear views, establishing, silhouettes |
| EWS | `an extreme wide shot` | No readable faces |

| Angle | Phrase |
|---|---|
| Eye level | `at eye level` |
| Front-facing | `front-facing toward the camera` |
| Three-quarter | `in a three-quarter view, turned slightly toward the camera` |
| Profile | `in clean side profile` |
| Over-the-shoulder | `over the shoulder of <Subject 2>, whose shoulder is softly blurred in the foreground` |
| Low | `from a slightly low angle` |
| High | `from a slightly high angle` |
| Overhead | `from directly overhead` |
| Rear | `from behind` |
| Dutch | `a tilted Dutch-angle medium shot` |

Face rules: dialogue/readable faces use CU, MCU, or MS, front-facing or three-quarter; at most two readable faces per shot. Wide/EWS is restricted to rear views, establishing shots, silhouettes, or cases where faces do not matter. Keep subjects centered or on inner thirds. Avoid `24mm`, `wide-angle lens`, `fisheye`, `ultra-wide`, `GoPro`, and `action cam` for shots with faces. Use an 85mm lens for CU/MCU and a 50mm lens for MS, with compressed perspective and natural proportions. Keep steady distance on face-visible tracking shots, use slow camera speed for wide framing, and have arrivals stop in a clear medium framing. Background extras are softly out of focus.

### A.5 Camera-move vocabulary and precision

Allowed amplitude modifiers are `with small amplitude` and `with large amplitude`; allowed speed modifiers are `at slow speed` and `at fast speed`. Omit medium amplitude and normal speed. Do not attach modifiers to Static, POV, or Shake. Required landing clauses use the substrings ` toward `, ` revealing `, ` onto `, and ` as ` for every move except Static, POV, and Shake. Omission on those three is a warning. A landing on those three is allowed. A modifier on those three is an error. Direction clauses (`from the front`, `from behind`, `from the side`, `moving backward`, `at a steady distance`, `smoothly`) are not a second move.

| Move family | Exact phrase |
|---|---|
| Static | `The camera holds a static shot` |
| Push / dolly in | `The camera pushes in` |
| Pull / dolly out | `The camera pulls out` |
| Zoom | `The camera zooms in` / `The camera zooms out` |
| Pan | `The camera pans left` / `The camera pans right` |
| Tilt | `The camera tilts up` / `The camera tilts down` |
| Truck | `The camera trucks left` / `The camera trucks right` |
| Pedestal | `The camera pedestals up` / `The camera pedestals down` |
| Arc / orbit | `The camera arcs around <Subject N>` |
| Tracking | `The camera tracks <Subject N>` |
| POV | `The camera holds <Subject N>'s point of view` |
| Shake | `The camera shakes slightly` / `The camera shakes strongly` |
| Roll | `The camera rolls clockwise` / `The camera rolls counterclockwise` |

Use the move as a sentence, not a list. A move describes camera position, direction, speed/amplitude when meaningful, the subject followed, and where the move lands. Static examples need not name a landing. No synonyms such as "drone shot", "moves left", or "slow zoom effect" count as official moves. Do not let a style opening add a second camera move. Avoid pulling, zooming, or pedestaling away from a readable face into a wide; fast motion with wide framing distorts faces.

Precision prose requirements: action beats form a causal chain (initial state → trigger → action → physical feedback → reaction); camera movement states where the camera starts, how it moves, and what it follows; emotion is expressed with visible micro-actions; subject identity, props, damage, lighting, and screen direction persist across cuts unless changed in the action; no generic quality tags such as `4k`, `masterpiece`, `high quality`, `epic`, `dynamic camera`, or `cool VFX`.

### A.6 Language and on-screen text vocabulary

Allowed language tags are `[English]`, `[Kannada]`, `[Hindi]`, `[Tamil]`, `[Telugu]`, `[Malayalam]`, `[Marathi]`, and `[Bengali]`. Dialogue must use its native script except English words in code-mixed dialogue. Pure romanization for a non-English line is rejected; any conversion helper must show original and proposed native-script text and require explicit user confirmation before use. Punctuation at the end is `.`, `?`, or `!`; replace terminal `।`/`॥` with `.`.

| Language tag | Script | Unicode range used by the Stage 0 presence check |
|---|---|---|
| `[English]` | Latin | Latin letters; no non-Latin script required |
| `[Kannada]` | Kannada | U+0C80–U+0CFF |
| `[Hindi]` | Devanagari | U+0900–U+097F |
| `[Tamil]` | Tamil | U+0B80–U+0BFF |
| `[Telugu]` | Telugu | U+0C00–U+0C7F |
| `[Malayalam]` | Malayalam | U+0D00–U+0D7F |
| `[Marathi]` | Devanagari | U+0900–U+097F |
| `[Bengali]` | Bengali | U+0980–U+09FF |

| Meaning | Kannada | Hindi | Tamil | Telugu | Malayalam |
|---|---|---|---|---|---|
| Go inside. | ಒಳಗೆ ಹೋಗು. | अंदर जाओ. | உள்ளே போ. | లోపలికి వెళ్ళు. | അകത്തേക്ക് പോ. |
| Come here. | ಇಲ್ಲಿ ಬಾ. | इधर आओ. | இங்கே வா. | ఇక్కడికి రా. | ഇവിടെ വാ. |
| Stop! | ನಿಲ್ಲು! | रुको! | நில்! | ఆగు! | നിൽക്ക്! |
| Tell the truth. | ಸತ್ಯ ಹೇಳು. | सच बताओ. | உண்மையைச் சொல். | నిజం చెప్పు. | സത്യം പറ. |
| Forgive me. | ನನ್ನನ್ನು ಕ್ಷಮಿಸಿ. | मुझे माफ़ कर दो. | என்னை மன்னித்துவிடு. | నన్ను క్షమించు. | എന്നോട് ക്ഷമിക്കൂ. |
| I didn't do anything. | ನಾನು ಏನೂ ಮಾಡಿಲ್ಲ. | मैंने कुछ नहीं किया. | நான் எதுவும் செய்யவில்லை. | నేను ఏమీ చేయలేదు. | ഞാൻ ഒന്നും ചെയ്തിട്ടില്ല. |
| Keep quiet. | ಸುಮ್ಮನಿರು. | चुप रहो. | பேசாமல் இரு. | నోరు మూసుకో. | മിണ്ടാതിരിക്ക്. |

These ready-made lines are suggestions only and require user confirmation. Kannada `ಹೋಗು` / `ಬಾ` is familiar/commanding; polite forms are `ಹೋಗಿ` / `ಬನ್ನಿ`.

Visible signs, labels, and captions are in straight double quotes and copied verbatim in their original script (example: `a weathered board reads "ಕೇಂದ್ರ ಕಾರಾಗೃಹ"`). Keep visible text to 1–3 words; if it is unimportant, describe the object without readable text. Do not request subtitles; add them in editing.

### A.7 Voice library and accents

Choose one voice ID per speaker and preserve it across all lines. Preserve the full paste phrase across all lines for that speaker; do not switch to `in the same … voice` (PF-06). The user's explicit voice reference `<Audio N>` replaces a library phrase and supplies timbre only; never copy its original words.

| ID | Name / age / pitch | Texture and pace | Typical roles | Exact paste phrase |
|---|---|---|---|---|
| F1 | Soft breathy, 18–25, mid-high | Airy, breathy, gentle; slow | Shy lead, young bride, romantic heroine | `in a soft, breathy young female voice with a slow, gentle pace` |
| F2 | Bright clear, 20–30, mid-high | Clear, bright, crisp; brisk | Confident heroine, student, reporter | `in a bright, clear young female voice with a lively, brisk pace` |
| F3 | Warm velvet, 28–40, mid | Warm, rounded, smooth; moderate | Mother, doctor, narrator, kind sister | `in a warm, velvety female voice in her thirties with a calm, even pace` |
| F4 | Low husky, 25–40, low | Husky, slightly smoky; unhurried | Rebel, femme fatale, hardened convict | `in a low, husky female voice with a slightly smoky texture and an unhurried pace` |
| F5 | Crisp authoritative, 35–50, mid-low | Firm, articulate, precise; measured | Woman officer, lawyer, judge, boss | `in a crisp, authoritative mid-low female voice with precise diction and a measured pace` |
| F6 | Fragile trembling, 20–35, mid-high | Thin, slightly trembling, hushed; hesitant | Guilty convict, victim, frightened witness | `in a thin, fragile young female voice with a slight tremble and a hesitant pace` |
| F7 | Rich matriarch, 50–65, low-mid | Rich, resonant, slightly gravelly; deliberate | Mother-in-law, matriarch, female don | `in a rich, resonant older female voice with a slight gravel and a deliberate pace` |
| F8 | Elderly frail, 65–80, mid | Papery, cracked, soft; slow with pauses | Grandmother, old villager | `in a frail, cracked elderly female voice with a slow pace and small pauses` |
| F9 | Playful sassy, 16–24, high | Bright, teasing, sing-song; quick | Comic friend, younger sister, college girl | `in a playful, high, teasing young female voice with a quick, sing-song rhythm` |
| F10 | Sweet melodic, 20–28, mid-high | Sweet, smooth, honeyed, softly musical; gentle/flowing | Female protagonist, heroine, innocent lead | `in a sweet, melodic young female voice, smooth and honeyed, with a gentle, flowing pace` |
| M1 | Deep gravelly, 45–60, low | Gravelly, weathered; slow/measured | Senior officer, don, father | `in a deep, gravelly middle-aged male voice with a slow, measured pace` |
| M2 | Resonant baritone, 30–45, low-mid | Smooth, resonant, full; steady | Hero, lead officer, lawyer | `in a smooth, resonant baritone male voice with a steady, confident pace` |
| M3 | Warm gentle, 25–35, mid | Soft, warm, slightly husky; relaxed | Romantic lead, kind brother, doctor | `in a warm, gentle young male voice with a soft husk and a relaxed pace` |
| M4 | Young energetic, 18–25, mid-high | Bright, light; fast | College boy, sidekick, younger brother | `in a bright, energetic young male voice with a fast, eager pace` |
| M5 | Stern commanding, 35–50, mid-low | Hard, clipped, projected; brisk staccato | Jail warden, inspector, army officer | `in a hard, clipped mid-low male voice with a brisk staccato pace` |
| M6 | Raspy menacing, 30–50, low | Raspy, half-whispered, dry; slow drawl | Villain, henchman, blackmailer | `in a low, raspy male voice, half-whispered, with a slow, menacing drawl` |
| M7 | Nasal comic, 25–45, mid-high | Nasal, reedy; quick/uneven | Comic constable, shopkeeper, side character | `in a reedy, slightly nasal male voice with a quick, uneven rhythm` |
| M8 | Elderly wise, 65–80, low-mid | Thin, cracked, warm; slow | Grandfather, priest, retired judge | `in a thin, cracked elderly male voice, warm but tired, with a slow pace` |
| M9 | Nervous thin, 20–35, mid | Thin, tight, breathy; rushed/stumbling | Accused man, clerk, informer | `in a thin, tight young male voice that rushes and stumbles over the words` |
| M10 | Soft-spoken calm, 25–40, mid-low | Soft, quiet, velvety, close-mic; slow/unhurried | Quiet hero, poet, gentle father, shy lover | `in a soft-spoken, quiet male voice, velvety and calm, with a slow, unhurried pace` |
| M11 | Deep villain bass, 35–55, very low | Deep bass, smooth, cold, resonant; slow/deliberate/controlled | Main villain, crime boss, corrupt politician | `in a very deep, cold bass male voice, smooth and resonant, with a slow, deliberate, menacing calm` |
| K1 | Girl, 6–10 | Small, high, clear | Child | `in a small, high, clear little girl's voice` |
| K2 | Boy, 6–10 | Small, bright, excited pace | Child | `in a small, bright little boy's voice with an excited pace` |

Allowed accent clauses, appended after the voice phrase only when relevant:

| Clause | Use |
|---|---|
| `with a light Indian English accent` | English lines by Indian characters |
| `speaking Kannada with a natural Bengaluru urban accent` | City Kannada; may mix English words |
| `speaking Kannada with a rustic North Karnataka accent` | Dharwad/Hubballi village characters |
| `speaking Kannada with a soft Mysuru accent` | Old-Mysuru region, polite register |
| `speaking Hindi with a Mumbai street accent` | Tapori/Bambaiya characters |
| `speaking formal, theatrical Hindi` | 1980s film-style heroes, villains, judges |
| `speaking Tamil with a Chennai accent` | Tamil characters |
| `speaking Telugu with a Hyderabad accent` | Telugu characters |
| `speaking Malayalam with a soft Kerala lilt` | Malayalam characters |
| `with a neutral American accent` | Non-Indian roles |
| `with a British accent` | Non-Indian roles |

For two speakers in one scene, choose clearly distinct voices by gender, age band, or pitch. Prison-drama suggestions: male officer M5 (M1 if senior), guilty female convict F6 (F4 if hardened), woman officer F5, kind older inmate F7/F8, comic constable M7.

### A.8 Delivery and visible-expression vocabulary

Delivery is rendered by §8.0 from this closed table. The model does not write it. `dialogue_lines.delivery` stores the id. Empty means `none`.

| Id | Verb | Manner, after the voice phrase and accent |
|---|---|---|
| `none` | `says` | none |
| `whisper` | `whispers` | `barely audible` |
| `shout` | `shouts` | `at full volume` |
| `command` | `orders firmly` | none |
| `mumble` | `mumbles` | `quietly, the words trailing off` |
| `sob` | `says through sobs` | `breath hitching between words` |
| `choked` | `says` | `voice catching` |
| `plead` | `pleads` | `with a rising, desperate tone` |
| `sarcastic` | `says` | `with dry sarcasm` |
| `tender` | `says softly` | `with a tender tone` |
| `menacing` | `says slowly` | `each word deliberate` |
| `cold` | `says` | `in a cold, flat tone` |
| `deadpan` | `says` | `completely deadpan` |
| `excited` | `exclaims` | `quickly and breathlessly` |
| `breathless` | `pants out the words` | `between heavy breaths` |
| `nervous` | `stammers` | `repeating the first word` |
| `laughing` | `says` | `while laughing` |
| `furious` | `says through clenched teeth` | `in a low, shaking voice` |
| `interrogation` | `asks sharply` | `each question clipped` |
| `murmur` | `murmurs` | `in a hushed undertone` |
| `singing` | `sings` | `softly, holding the last note` |

Voiceover replaces the verb with `says in an off-screen voiceover` and still appends the manner when the delivery has one. Lyrics of a sung line stay inside `<d>`.

Expression snippets are examples, not mandatory fixed text; each must remain physically observable:

| Expression | Example clause |
|---|---|
| Neutral, composed | `her face is calm and composed, her gaze steady, her lips relaxed` |
| Guilt | `she lowers her head, her eyes downcast and unable to meet his, her lips pressed together, her shoulders slightly hunched` |
| Shame | `she turns her face partly away, her cheeks tense, her eyes fixed on the floor, one hand gripping her sleeve` |
| Strict, stern | `his jaw is set, his brows drawn slightly together, his eyes hard and unblinking, his mouth a flat line` |
| Contempt | `one corner of his mouth lifts in a faint sneer, his eyelids half-lowered as he looks down at her` |
| Controlled anger | `his nostrils flare, his jaw tightens, and a vein shows at his temple while his voice stays low` |
| Rage | `her eyes widen and blaze, her brows drop hard, her teeth show as she shouts` |
| Fear | `her eyes widen, her breathing turns quick and shallow, and she presses back against the wall` |
| Shock | `his eyes snap wide, his mouth falls slightly open, and he freezes mid-step` |
| Grief | `her face crumples, her chin trembles, and tears spill down her cheeks` |
| Holding back tears | `her eyes glisten, she swallows hard and blinks rapidly, forcing her lips into a tight line` |
| Relief | `her shoulders drop, she lets out a long breath, and a small, tired smile appears` |
| Respect | `she looks up at him with a quiet, steady gaze and gives a small, respectful nod` |
| Subtle attraction | `her eyes linger on him a moment longer than needed, a small warm smile forms, and she lowers her gaze softly` |
| Shy | `she smiles with her lips closed, glances up through her lashes, then looks away` |
| Tender love | `his eyes soften, a gentle smile spreads slowly, and he tilts his head toward her` |
| Joy | `her face breaks into a wide, open smile, her eyes crinkling at the corners` |
| Suspicion | `his eyes narrow slightly and flick from her face to her hands and back` |
| Defiance | `she lifts her chin, holds his stare without blinking, and her lips press into a hard line` |
| Exhaustion | `her eyelids are heavy, her face pale, and her shoulders sag as she leans on the bars` |
| Pleading | `her brows rise in the middle, her eyes wet and wide, her hands pressed together in front of her chest` |
| Menace | `he smiles slowly without it reaching his eyes, his head tilted slightly, watching her` |
| Regret | `he closes his eyes for a moment, exhales through his nose, and his mouth tightens` |
| Determination | `his gaze hardens and fixes ahead, his jaw squares, and he gives one short nod` |

When expression changes within a shot, describe the visible transition (for example, annoyance softens into hurt as brows relax and eyes drop). Describe non-verbal gasps/sobs/sighs only when allowed by the clip audio policy.

### A.9 REF2VA labels, task types, definitions, and retention

Reference labels are assigned in global attach/upload order, while numbering independently by kind: images `<Picture 1>…`, videos `<Video 1>…`, audio `<Audio 1>…`. Reordering updates affected labels and stales generated prompts. Do not use `<Image N>`.

Task types and triggers:

| Prefix | Trigger |
|---|---|
| `reference generation` | One or more references guide identity, scene, style, motion, or camera, without being literal frames |
| `keyframe completion` | An image is a first frame, keyframe, last frame, or concrete composition anchor |
| `video editing` | User explicitly requests changes to a source video; require at least one video; summary paragraph starts `The target video is an edited version of <Video K>.`, K the lowest video ordinal |
| `video continuation` | User explicitly requests continuation from a source video; require at least one video; no second fixed sentence |
| `audio reuse` | User explicitly requests reuse of the same audio signal; require at least one audio reference |
| `audio reference` | Audio is used only for voice timbre, style, rhythm, or texture |

Defaults may select `reference generation` when a guidance reference is present, `keyframe completion` for a frame/composition anchor, and `audio reference` when audio is used only as timbre. Never automatically select `video editing`, `video continuation`, or `audio reuse`. The mere presence of video or audio does not imply a task type. The user confirms selected types.

| Area | Allowed marker |
|---|---|
| Visual | `fully_preserved`, `partially_preserved`, `attribute_transfer`, `weak_reference` |
| Audio | `fully_copy`, `partially_copy`, `reference`, `weak_reference` |

Retention entries are one per line:

```text
<Subject N> (appears in [Shot 1], [Shot 3]): fully_preserved - reason.
<Picture N> ([Shot 1] first frame): fully_preserved - reason.
<Video N> (cut and pacing structure): weak_reference - reason.
<Audio N>: reference - reason.
```

Picture parentheticals name the actual role (`first frame`, `keyframe`, `last frame`, `composition anchor`, or `framing reference`); video parentheticals describe its contribution; audio needs no parenthetical. Reasons are approximately 20 words and at most 25 words. Never put `(Sx)` in retention analysis. Added actions/plot are not themselves a loss of reference fidelity.

Default retention mapping is §8.6: person, location, and `other` subjects, plus every picture anchor, use `fully_preserved`; outfit and prop subjects use `partially_preserved`; every video uses `weak_reference`; audio selected as `audio reuse` uses `fully_copy`; every other audio uses `reference`. An outfit or prop picture linked on a person does not change that person's marker. The user may change every default. The LLM supplies reason prose only; Python creates each entry and checks marker membership.

Deterministic subject-definition formulas:

- Person (0 pictures): `<Subject N> is the {role_phrase}[, {appositive},] with {pronoun} appearance, facial features, build, and complete {outfit_noun} defined by text alone.`
- Person (1 picture): `<Subject N> is the {role_phrase} in <Picture M>[, {appositive},] with {pronoun} face, hair, build, and complete {outfit_noun} taken exactly from the reference.` Omit `in <Picture M>` if there is no linked picture. `role_phrase` is a short noun (not a picture description); `pronoun` is `his`, `her`, or `its`; `appositive` is optional and appears with both surrounding commas; `outfit_noun` is a concrete term such as `outfit` or `uniform`.
- Person (multiple pictures): When a person links an identity anchor image <Picture M> and an outfit image <Picture P>: `<Subject N> is the {role_phrase} with {pronoun} face, hair, and build taken from <Picture M>[, {appositive},] and {pronoun} complete {outfit_noun} taken from <Picture P>.`
- Location: `<Subject N> is the {role_phrase} in <Picture M>, including its {feature_list} exactly as shown.` If no picture is linked, `<Subject N> is the {role_phrase}, including its {feature_list} defined by text alone.` Feature lists are explicit nouns and end with `and layout` when layout is included.
- Outfit-only: `<Subject N> is the {role_phrase} in <Picture M>, with its complete appearance and design taken exactly from the reference.` `role_phrase` identifies the garment or outfit.
- Prop: `<Subject N> is the {role_phrase} in <Picture M>, with its shape, material, color, and distinctive details taken exactly from the reference.` Include only properties visible in the reference.
- Picture anchor: `<Picture N> is the {role} for [Shot X], defining {defines_text}.` The role is one of `composition anchor`, `framing reference`, `first frame`, `keyframe`, `last frame`; default `defines_text` is `the layout`.
- Audio: `<Audio N> is the voice-timbre reference for <Subject N> (Sx).` When the speaker has no subject, use the persona in place of `<Subject N>`.

Person formula selection: (1) When 0 pictures are linked, emit the 0-picture text-only formula. (2) When 1 picture is linked (or when multiple pictures link the same role), the lowest-ordinal image with role `identity_anchor` (or fallback `outfit`, `prop`, `location`) is named in the standard 1-picture formula. (3) When distinct pictures are linked for identity and outfit, the multi-picture formula combines `<Picture M>` (lowest `identity_anchor`) and `<Picture P>` (lowest `outfit`). An `outfit` or `prop` role on a person does not change the person sentence unless linked as above; a separate outfit or prop subject gets its own line. The same reference may also have a frame, composition, or framing role: that role emits a picture-anchor line in addition to the subject line. `defines_text` blank renders as `the layout`.

Line order is subjects by ordinal, then picture-anchor lines by picture ordinal and role order `first_frame`, `keyframe`, `last_frame`, `composition_anchor`, `framing_reference`, then audio lines by audio ordinal and speaker number. `role_phrase`, `appositive`, and `outfit_noun` contain no comma. A location with an empty `feature_list` fails Stage 0.

In `subject_definitions`, do not describe a reference image's visual contents in free prose; identify it by its label and role. Shot prose may describe the scene. First appearance of a subject in a shot states its position and action; subsequent shots reuse the same label without redefining identity. Frame-anchor prose uses `the shot begins from <Picture N>`, `the shot's keyframe corresponds to <Picture N>`, or `the shot ends on <Picture N>`.

### A.10 Style vocabulary and exact openings

For `plain`, the non-REF prefix is `[Shot 1] ` plus the chosen pair plus a comma, for example `[Shot 1] Live-action, cinematic,`. The renderer inserts one space and then the shot prose, whose size is whatever that shot uses. The words `a medium close-up frames` are not part of any prefix. `plain` permits the following opening pairs only: `Live-action, cinematic`; `2D-animated, cinematic`; `3D CG, cinematic`; `claymation, cinematic`; `watercolor, cinematic`; `vintage film, cinematic`. The default is `Live-action, cinematic`. For all styles, preserve the look of a supplied frame when it conflicts with a style preference. The dialogue-only sentence in §A.3 overrides any style-specific sound direction.

| Style | REF2VA opening (exact) | T2VA / frame-mode opening (exact prefix) |
|---|---|---|
| 80s Bollywood | `The target video is in the style of a 1980s Hindi masala film shot on 35mm, with visible film grain, a saturated warm Eastmancolor palette, soft diffusion glow on highlights, hard studio key lighting, slightly faded blacks, and natural proportions.` | `[Shot 1] Vintage film, 1980s Hindi masala-film look on grainy 35mm with saturated warm colors and soft diffusion glow,` |
| Cinematic modern | `The target video is in a modern cinematic feature-film style with motivated low-key lighting, a teal-and-amber color grade, rich contrast, fine film grain, shallow depth of field, and natural proportions.` | `[Shot 1] Live-action, cinematic, modern feature-film look with motivated low-key lighting and shallow depth of field,` |
| Modern series | `The target video is in a modern streaming-drama style with naturalistic soft lighting, a muted, slightly desaturated color grade, realistic skin texture, gentle contrast, and natural proportions.` | `[Shot 1] Live-action, streaming-drama look with naturalistic soft lighting and a muted grade,` |
| Noir thriller | `The target video is in a neo-noir crime-thriller style with hard low-key lighting, deep black shadows, sodium-orange and cold cyan accents, wet reflective surfaces, light film grain, and natural proportions.` | `[Shot 1] Live-action, cinematic neo-noir look with hard low-key lighting and deep shadows,` |

Style vocabulary:

| Style | Lighting, color, lens, movement, performance |
|---|---|
| 80s Bollywood | Visible 35mm grain, slight gate weave, faded blacks, occasional dust specks, soft halation; saturated reds/magentas/emeralds/golds and warm skin; hard frontal studio key, colored gel backlights, flat daylight; zoom lenses and crash zooms on close-ups, static frontal compositions, low-angle hero shots; theatrical delivery, dramatic pauses; period-appropriate sets/costumes only. |
| Cinematic modern | Motivated practical light, one named source per shot, side key/negative fill/rim light, optional volumetric shaft; teal/amber or restrained single-hue grade; 85mm faces, 50mm mediums, optional anamorphic oval bokeh/subtle flares; slow push-ins, smooth tracking, static performance holds, occasional slow arc; restrained, internal acting. |
| Modern series | Soft window/daylight or practical lamps, low contrast and readable faces; muted/desaturated greys/greens by day and sodium amber by night; 85mm close-ups/50mm mediums with moderate depth of field; coverage, OTS, static confrontations, slight handheld intimacy, slow push-in for key lines; understated naturalistic performance. |
| Noir thriller | Single hard source, deep shadow, blind/bar shadows, haze in beams; near-monochrome with one sodium-orange/cyan/red accent and wet reflective surfaces; 85mm close-ups, 50mm mediums, deep focus for paranoia; slow push-ins, static holds, slight Dutch angles, POV through bars/blinds, rear tracking; still, guarded performance, at least one eye and mouth lit on a speaking face. |

Sound suggestions when and only when custom sound is selected: 80s style may use exaggerated foley or orchestral/synth/tabla instrumentation; cinematic modern may use room tone, cloth, breath, distant city, sustained low strings, sparse piano, analog pads, or pulsing bass; modern series may use fans, traffic, phones, household appliances, soft synth, muted guitar, or low pulse; noir may use rain, drips, sirens, buzzing neon, footsteps, pulsing synth bass, muted trumpet, brushed snare, or low drones. These suggestions do not override the dialogue-only default.

### A.11 Phrase bank, troubleshooting rules, and product conventions

Approved reusable framing phrases:

- `framed at eye level in a medium close-up, front-facing, shot on an 85mm lens with compressed perspective and natural proportions`
- `centered in the frame, the camera keeps a steady distance`
- `their faces stay clear, natural and undistorted`
- `the background falls into soft, shallow depth of field`
- `seen from behind in a wide shot, their faces not visible`

Troubleshooting is performed as prompt correction first. For warped faces, move to MCU/MS, center, use 85mm/50mm language, steady distance, and slow camera speed; prefer 2K when available. For identity drift, reduce shot count and angle changes, explicitly reuse the same subject label, and never describe features that contradict its reference. For invented rooms, define a location subject and optionally a composition anchor. For door teleportation, state hinge side and direction in a separate action beat. Repeat visible props in every shot where they appear. For camera drift, use an official move and one move per shot. For wrong speech attribution, put `<Subject N> (Sx)` immediately before the speaking verb and keep listeners' lips closed. For an incorrect mode, select one that matches literal-frame vs. reference intent; never combine frame roles and reference roles. Correct timestamp syntax and ratio, use only defined labels, and keep the prompt `body` within 7000 Unicode code points.

Export-specific product rules (not external H3 API requirements): prompt filename `clip-<NN>-<D>s.txt`; collision on `NN` alone; REF2VA companion `clip-<NN>-PLATES.txt`; one PLATES line per reference in global attach order, formatted `<Label>: <filename-or-MISSING> — <role>: <caption>`; UTF-8, LF, no BOM, one final newline. Never infer a different layout from a user's directory contents.

The explicit PF-08b mood-word warning vocabulary is: `angry`, `anxious`, `calm`, `dark`, `dreamy`, `emotional`, `epic`, `fearful`, `happy`, `hopeful`, `joyful`, `melancholic`, `menacing`, `mysterious`, `ominous`, `peaceful`, `romantic`, `sad`, `scary`, `suspenseful`, `tense`, `tragic`, `uplifting`. `tense` and `sad` are errors; the remaining entries are warnings in music prose. Matching is case-insensitive, token-boundary based. Additions to this lexicon require a specification revision.

---

## Approval

v1.6 was certified on 2026-11-05. v0.2 was updated on 2026-11-05. This document, **v0.3**, is certified on 2026-11-06 as the final locked implementation contract, superseding all prior revisions and incorporating the flat REF2VA canvas, lightweight reference tokens, many-to-many picture linking, and consolidated preflight safeguards. The H3 rules and the Section 12 and Section 16 defaults are unchanged. The listen port is customizable under §5.7. Health `specification_version` is `0.3`. All code, UI, prompts, and tests trace back to this document.

**Certification statement:** The H3 templates, limits, vocabularies, formulas, and validation rules are specified above. §17 records the required runtime paths and the local reference paths. The process URL uses the resolved listen port. Implementations use the runtime paths. They do not consult the reference files to create or validate a prompt.
