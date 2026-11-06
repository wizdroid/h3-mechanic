# H3 Prompt Studio

> **Precision Local Prompt Studio for MiniMax Hailuo 02 (MiniMax-H3 & MiniMax-H3-Max)**  
> **Specification Version:** `0.3 (Final Locked)` · **Stack:** Python 3.10+ (FastAPI, Uvicorn, httpx, jsonschema, SQLite WAL) + Nord Vanilla JS Web UI + Local Ollama LLM.

---

## 1. Overview

**H3 Prompt Studio** is a deterministic, local-first studio engineered to author, validate, repair, and export production-ready prompts for the **MiniMax Hailuo 02** video generation foundation model series (**MiniMax-H3** and **MiniMax-H3-Max**).

Unlike standard chatbots or generic prompt wrappers, H3 Prompt Studio employs a **two-tier architecture**:
1. **Creative Drafter (Local LLM via Ollama):** Generates cinematic shot plans, scene staging, lighting, and action pacing without ever seeing or corrupting native dialogue scripts or character tokens.
2. **Deterministic Compiler (Python Engine):** Formulates exact byte-level instruction lines, expands dialogue lines into canonical 8-part speech sentences with verified lip closures, links reference plates, and enforces MiniMax model constraints.

### The Five Video Generation Modes

| Mode | Target Workflow | Output Layout & Rules |
|---|---|---|
| **T2VA** | Text-to-Video-Audio | Single multimodal description field + sound fields. Generates camera choreography, visual style, atmosphere, and verbatim dialogue in 8 languages. Concrete aspect ratio required (e.g. `16:9`, `21:9`). |
| **I2VA** | Image-to-Video-Audio | Single image reference. Starts with code-generated instruction line: `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` Aspect ratio strictly locked to `adaptive`. |
| **FL2VA** | First-Last-Frame-to-Video-Audio | Two-image interpolation. Starts with instruction line aligning Picture 1 at `0.00`s and Picture 2 at final duration `S.SS`s. Supports 1-shot camera journeys (Criterion A-12). Aspect ratio locked to `adaptive`. |
| **L2VA** | Last-Frame-to-Video-Audio | Single image continuation. Starts with instruction line landing on `<Picture 1>` at final duration `S.SS`s. Aspect ratio locked to `adaptive`. |
| **REF2VA** | Multi-Reference-to-Video-Audio | Flat single-canvas interface supporting up to 9 images, 3 videos, 3 audio files, and many-to-many subject linking (0, 1, or multiple pictures per subject across extensive categories: characters, animals, dinosaurs, creatures, robots, objects, props, locations). Features per-shot **Action & Events** choreography to direct multi-subject staging, assembles 6 canonical prompt sections, and generates companion ComfyUI `PLATES.txt` files. |

---

## 2. Prerequisites

1. **Operating System:** Linux, macOS, or Windows (WSL2 recommended for Windows).
2. **Python:** Version `3.10` or higher (`3.11`, `3.12`, or `3.14` tested).
3. **Ollama:** Installed and running locally.
   - Download: [ollama.com](https://ollama.com)
   - Ensure Ollama is running at `http://127.0.0.1:11434`.
4. **Local Drafter Model:**
   - Tuned specifically for `qwen2.5:7b-instruct`:
     ```bash
     ollama pull qwen2.5:7b-instruct
     ```
   - Other supported models include `mistral-nemo`, `llama3.1:8b-instruct`, or `qwen2.5:14b-instruct`.

---

## 3. Installation & Setup

### Step 1: Clone and Set Up Virtual Environment

```bash
git clone https://github.com/example/h3-mechanic.git
cd h3-mechanic

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Step 2: Install Pinned Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Launch the Studio

```bash
# Start with default port 9013
uvicorn app.main:app --host 127.0.0.1 --port 9013
```

Open your browser to:
[http://127.0.0.1:9013](http://127.0.0.1:9013)

On initial launch, the application automatically:
- Creates required runtime directories: `data/`, `data/exports/`, `data/backups/`, `data/logs/`.
- Initializes the SQLite database (`data/h3studio.db`) with Foreign Keys, WAL mode, and busy timeouts.
- Executes schema migrations (`0001_initial.sql`).
- Recovers any interrupted generation tasks.

---

## 4. Configuration & Security

The server is strictly designed for secure local operation:

- **Loopback Host Enforcement (§5.7):** The studio only binds to `127.0.0.1`. Setting `H3_HOST` to any external IP aborts startup immediately to prevent DNS rebinding or unauthorized LAN exposure.
- **Dynamic Port Resolution (§5.7):**
  1. `H3_PORT` environment variable (if set, must be an integer between 1 and 65535).
  2. `settings` table `listen_port` configured in the UI Settings tab.
  3. Default fallback: `9013`.
  ```bash
  export H3_PORT=9050
  uvicorn app.main:app --host 127.0.0.1 --port 9050
  ```
- **Security Middleware:** Validates loopback `Host` header and inspects browser `Origin` headers on mutating HTTP requests (`POST`, `PUT`, `DELETE`), rejecting unrecognized origins with HTTP 403.
- **Concurrency Lock:** Process-wide `asyncio.Lock` guarantees single-flight LLM generations. Concurrent generation requests receive HTTP 409 `busy` with the active clip ID.
- **Optimistic Concurrency:** Protects multi-tab editing via `If-Match: <revision>` headers, returning HTTP 412 `precondition` if the clip was edited in another session.

---

## 5. Quick Start: Authoring a T2VA Clip in 4 Steps

1. **Select Mode:** Open the studio and click the **T2VA** tab under the Generator view.
2. **Configure Clip Parameters:**
   - **Name:** "Corridor Pursuit"
   - **Video Model:** `MiniMax-H3` (4–15s, 768P/2K) or `MiniMax-H3-Max` (5–15s, 480P/768P).
   - **Duration:** `8s`
   - **Ratio:** `16:9` (or `21:9`, `4:3`, `1:1`, `9:16`)
   - **Style:** `Live-action, cinematic` (or select from 10 named cinematic presets).
3. **Add Seed & Dialogue:**
   - Enter a creative seed: *"A detective in a trench coat searches a rainy alleyway at night."*
   - Add a dialogue line: Speaker `Detective`, Language `English`, Delivery `whisper`, Text *"Stay quiet. He's nearby."*
4. **Generate & Export:**
   - Click **Generate Prompt**. Watch the real-time NDJSON stream compile the JSON shot plan, compose prose, and insert canonical dialogue speech sentences.
   - Observe the **Preflight Validation** badge change to green (`Pass: 0 errors`).
   - Click **Export Clip**. The studio atomically saves the prompt to `data/exports/clip-01-8s.txt` and archives a rollback snapshot to `data/backups/`.

---

## 6. Directory Structure

```text
h3-mechanic/
├── app/
│   ├── api/                 # FastAPI REST and NDJSON streaming endpoints
│   │   ├── export_routes.py     # Atomic prompt & PLATES exporter, NN collision engine
│   │   ├── frame_routes.py      # I2VA, FL2VA, L2VA reference management
│   │   ├── llm_routes.py        # Ollama models proxy, generation & fix streaming
│   │   ├── ref2va_routes.py     # REF2VA subjects, links, shots, task types
│   │   ├── t2va_routes.py       # T2VA clip setup, dialogue & speakers CRUD
│   │   └── validation_routes.py # Preflight validation & heuristic overrides
│   ├── config.py            # Environment configuration, directory setup, port resolution
│   ├── engine/              # Deterministic prompt compilers and atomic exporter
│   │   ├── exporter.py          # Atomic file writing, NN collision, JSON snapshot manager
│   │   ├── placeholders.py      # Placeholder protocol ({{Lk}}, {{Tm}}) parser & mapper
│   │   ├── renderer.py          # Deterministic renderer, speech sentence builder, 6-section REF2VA
│   │   └── subject_builder.py   # Deterministic subject definitions compiler (S-03 formulas)
│   ├── llm/                 # Local LLM integration & concurrency controls
│   │   ├── client.py            # Async httpx client for Ollama /api/tags, /show, /generate
│   │   ├── lock.py              # Single-flight asyncio concurrency lock
│   │   ├── pipeline.py          # Multi-stage prompt elaboration & prose writer engine
│   │   └── schemas.py           # Strict JSON schemas for LLM structured outputs
│   ├── middleware/          # Security & Host validation middleware
│   ├── resources/           # Bundled normative reference vocabularies (JSON)
│   ├── storage/             # SQLite migrations, WAL configuration, database connection
│   ├── validation/          # Preflight validation engine & estimators
│   │   ├── estimators.py        # Syllable counters, speech duration estimators, speaker numbering
│   │   ├── parser.py            # Canonical prompt parser (ParsedPrompt)
│   │   ├── registry.py          # Preflight rule registry & autofix engine
│   │   └── rules/               # Preflight rules PF-01 through PF-35
│   └── web/                 # Vanilla JS ES modules & Nord theme CSS
│       ├── css/nord.css         # Nord Dark, Coloured, and Light stylesheets
│       ├── index.html           # Single-page web studio shell
│       └── js/                  # Frontend view controllers & state management
├── data/
│   ├── backups/             # Atomic JSON rollback snapshots (last 5 per clip)
│   ├── exports/             # Exported .txt prompts and -PLATES.txt files
│   └── h3studio.db          # SQLite WAL database
├── docs/
│   ├── implementation/      # Phased engineering blueprints and resume checkpoints
│   └── specifications/      # Specification 0.3 (Final Locked normative contract)
├── tests/                   # Pytest automated test suites (Stages 01–08)
├── requirements.txt         # Pinned Python dependencies
└── README.md                # This document
```

---

## 7. Testing & Quality Assurance

H3 Prompt Studio includes a comprehensive test suite certifying full compliance with the 49 Acceptance Criteria defined in Section 13 of `specification-0.3.md`:

```bash
# Run the entire test suite
.venv/bin/pytest tests/ -v

# Run a specific stage
.venv/bin/pytest tests/test_stage_01.py -v  # Scaffolding, DB & Health
.venv/bin/pytest tests/test_stage_02.py -v  # Preflight Rules PF-01 to PF-35
.venv/bin/pytest tests/test_stage_03.py -v  # Deterministic Renderer & Exporter
.venv/bin/pytest tests/test_stage_04.py -v  # Ollama Client & Concurrency Lock
.venv/bin/pytest tests/test_stage_05.py -v  # Generator Shell & T2VA Pipeline
.venv/bin/pytest tests/test_stage_06.py -v  # Frame Modes (I2VA, FL2VA, L2VA)
.venv/bin/pytest tests/test_stage_07.py -v  # REF2VA Flat Canvas & Linking
```

---

## 8. Troubleshooting

| Issue / Error | Root Cause | Solution |
|---|---|---|
| **Ollama connection failed** | Ollama daemon is not running on `127.0.0.1:11434`. | Start Ollama using `ollama serve` or launch the Ollama desktop application. |
| **Model not found in dropdown** | No models pulled or Ollama tags empty. | Run `ollama pull qwen2.5:7b-instruct` in your terminal and click **[Test / Refresh]** in Settings. |
| **HTTP 409 `busy`** | Another generation, fix, or variation task holds the process lock. | Wait for the active generation to complete, or click **Cancel Generation**. |
| **HTTP 412 `precondition`** | The clip was modified in another browser tab (revision mismatch). | Reload the tab to synchronize with the latest state in SQLite. |
| **Preflight Error PF-30 (Stale Prompt)** | Clip inputs (duration, dialogue, references) were edited after generation. | Click **Generate Prompt** to re-run generation matching current inputs. |
| **Preflight Error PF-31 (Native Script)** | Non-English dialogue was entered in Romanized script (e.g. `namaskara`). | Enter the line using the native Unicode script (e.g. `ನಮಸ್ಕಾರ` for Kannada or `नमस्ते` for Hindi). |
| **Export HTTP 409 `collision`** | A file with the same integer clip number already exists in `data/exports/`. | Choose an unused clip number or check **Overwrite Existing** in the export dialog. |

---

## 9. License & Normative Contract

This project is governed strictly by [`docs/specifications/specification-0.3.md`](docs/specifications/specification-0.3.md). All rights reserved.
