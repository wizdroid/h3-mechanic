# Stage 01: Core Scaffolding, Storage & Health Endpoint

**Milestone:** M0  
**Specification Reference:** [`specification-0.3.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.3.md) §§5.1, 5.2, 5.6, 5.6.1, 5.7, 6.1, 17.1, 17.2  
**Key Acceptance Criteria:** A-20, A-35, A-48, A-49  

---

## 1. Stage Overview & Scope

Establish the production-grade application skeleton, database migration engine, SQLite schema, security middleware, and the specification-verified `/api/health` endpoint.

### Deliverables:
1. `requirements.txt`: Pinned Python dependencies (`fastapi`, `uvicorn[standard]`, `httpx`, `jsonschema`, `pytest`, `pytest-asyncio`).
2. `app/config.py`: Directory and path resolution, listen port resolution chain (`H3_PORT` → `settings` → `9013`), `127.0.0.1` host verification.
3. `app/storage/db.py`: Database connection pool with enforced PRAGMAs (`foreign_keys = ON; journal_mode = WAL; busy_timeout = 5000;`).
4. `app/storage/migrations/0001_initial.sql`: Complete DDL schema per §6.1 with all tables, constraints, and indexes.
5. `app/storage/migration_runner.py`: Forward-only migration manager with pre-migration database snapshot backup.
6. `app/middleware/security.py`: Loopback binding and DNS-rebinding / CSRF Origin/Host validation.
7. `app/main.py`: FastAPI app instance with lifecycle hooks and `/api/health` route.
8. `tests/test_stage_01.py`: Automated pytest suite verifying all Stage 01 acceptance criteria.

---

## 2. Step-by-Step Implementation Instructions

### Step 1.1: Dependencies (`requirements.txt`)
Create `requirements.txt` pinning exact versions:
```text
fastapi>=0.110.0,<0.116.0
uvicorn[standard]>=0.28.0,<0.35.0
httpx>=0.27.0,<0.29.0
jsonschema>=4.21.0,<4.24.0
pydantic>=2.6.0,<2.11.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

### Step 1.2: Configuration & Path Resolution (`app/config.py`)
Implement the configuration module enforcing the §17 paths:
- Root directory: `/home/wizdroid/Applications/h3-mechanic`
- Data directories: `data/`, `data/exports/`, `data/backups/`, `data/logs/` (auto-created on startup).
- Port resolution order (§5.7, Criterion A-49):
  1. `os.environ.get("H3_PORT")` (stripped; must be integer 1–65535).
  2. Database `settings.listen_port` (if exists).
  3. Default: `9013`.
- Host resolution: `os.environ.get("H3_HOST", "127.0.0.1")`. Abort startup immediately if host is not `127.0.0.1`.

### Step 1.3: SQLite Engine & Migration Manager (`app/storage/`)
- `db.py`: Every connection must execute:
  ```python
  cursor.execute("PRAGMA foreign_keys = ON;")
  cursor.execute("PRAGMA journal_mode = WAL;")
  cursor.execute("PRAGMA busy_timeout = 5000;")
  ```
- `migration_runner.py`:
  - Reads `schema_version` table.
  - Backs up DB to `data/backups/h3studio-pre-migration-<timestamp>.db` before applying migrations.
  - Executes unapplied migrations in alphabetical transaction blocks.
  - Aborts startup if on-disk schema version exceeds application's known migrations.
- `migrations/0001_initial.sql`: Exact DDL from §6.1:
  - `projects`, `clips`, `references_tokens`, `subjects`, `subject_pictures`, `shots`, `speakers`, `dialogue_lines`, `onscreen_texts`, `retention_markers`, `prompts`, `settings`.
  - Include all `CHECK` constraints (e.g. `duration_s BETWEEN 4 AND 15`, `pronoun IN ('his','her','its')`, `width_px > 0`, `duration_ms BETWEEN 2000 AND 15000`).

### Step 1.4: Security Middleware (`app/middleware/security.py`)
Per §5.7 & Criterion A-35:
- Check `request.headers.get("host")`: Allow only `localhost`, `127.0.0.1`, `[::1]`, or `127.0.0.1:<port>`. Return HTTP 403 otherwise.
- For mutating HTTP methods (`POST`, `PUT`, `DELETE`, `PATCH`): If `Origin` header is present, require it to match `http://127.0.0.1:<port>` or `http://localhost:<port>`. Return HTTP 403 otherwise.

### Step 1.5: FastAPI Entrypoint & Health Route (`app/main.py`)
- Lifespan handler: runs directory creation and database migrations on startup.
- Endpoint `GET /api/health`:
  - Status 200 JSON response:
    ```json
    {
      "status": "ok",
      "specification_version": "0.3",
      "schema_version": 1,
      "ollama": "unreachable",
      "model_count": 0,
      "bind": "127.0.0.1:9013"
    }
    ```
  - `specification_version` must be exactly `"0.3"`.
  - `bind` must reflect the actual bound port.

---

## 3. Calibrated Master Prompt for Stage 01

```text
You are an expert systems engineer implementing Stage 01 of H3 Prompt Studio strictly according to docs/specifications/specification-0.3.md.

Task:
Implement the core scaffolding, configuration, storage engine, security middleware, and /api/health endpoint.

Strict Boundaries:
1. All file paths must be absolute or relative to the workspace root: /home/wizdroid/Applications/h3-mechanic.
2. The SQLite schema must match Section 6.1 of specification-0.3.md verbatim:
   - PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;
   - All CHECK constraints must be enforced in 0001_initial.sql.
   - references_tokens: width_px and height_px are optional positive integers; duration_ms is between 2000 and 15000.
   - clips.wizard_step defaults to 1.
3. Configuration and Port Resolution:
   - Check H3_PORT environment variable -> settings table -> 9013 default.
   - Only 127.0.0.1 is permitted as H3_HOST. Abort if any other host is set.
4. Security Middleware:
   - Validate Host header: allow only localhost/127.0.0.1.
   - Validate Origin header on mutating methods: reject non-matching origins with 403.
5. GET /api/health:
   - Must return specification_version: "0.3" exactly.
   - bind must be "127.0.0.1:<bound_port>".
6. Tests:
   - Create tests/test_stage_01.py verifying database PRAGMAs, foreign key cascades, migration snapshot backups, Host/Origin blocking (403), and /api/health.

Do not implement UI or LLM pipeline logic in this stage. Output production-ready, clean, well-commented Python code and SQL files.
```

---

## 4. Integrated Verification Checkpoints

Run the automated verification suite:
```bash
pytest tests/test_stage_01.py -v
```

### Checkpoint Verifications:
1. **Health Verification:**
   - Execute: `curl -s http://127.0.0.1:9013/api/health`
   - Assert: `"specification_version":"0.3"` and `"status":"ok"`.
2. **Security Verification:**
   - Execute: `curl -s -H "Host: evil.com" http://127.0.0.1:9013/api/health`
   - Assert: HTTP 403 Forbidden.
3. **Database Constraints Verification:**
   - Insert invalid clip duration (`duration_s = 3` for `MiniMax-H3`) → Assert `sqlite3.IntegrityError`.
   - Delete parent clip → Assert child rows in `shots` and `dialogue_lines` cascade delete.
