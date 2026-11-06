# Last Development Stage: Final Integration, System Hardening & Acceptance Certification

This directory documents the **Final Development Stage (Stage 08 / Milestone M7)** of H3 Prompt Studio, establishing the definitive production handoff, system-wide hardening, and full verification against [`specification-0.3.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/specifications/specification-0.3.md).

---

## 1. Directory Contents

| Document | Purpose |
|---|---|
| [`08-settings-hardening-and-final-acceptance.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/implementation/stages/last/08-settings-hardening-and-final-acceptance.md) | Complete engineering guide and calibrated execution prompt for Stage 08. |
| [`RESUME_CHECKPOINT.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/implementation/stages/last/RESUME_CHECKPOINT.md) | Standardized state-tracking document used to record progress, test results, and resumption instructions. |
| [`README.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/implementation/stages/last/README.md) | This document — final release packaging, handoff certification, and acceptance overview. |

---

## 2. Final Stage Verification & Acceptance Overview

The final stage is not merely a feature addition; it is the **certification gate** that validates the entire end-to-end implementation across all modes and pipelines.

### Acceptance Scope Summary:

```
┌ 49-Point Acceptance Audit ─────────────────────────────────────────────┐
│ • A-01 to A-07 : Mode Behaviors (T2VA, I2VA, FL2VA, L2VA, REF2VA)      │
│ • A-08 to A-12 : Validation Engine, Limits, and FL2VA 1-Shot Waiver   │
│ • A-13 to A-16 : Local Ollama Integration, Schemas & Fail-Fast Guards │
│ • A-17 to A-21 : Atomic Exporter, Integer NN Collisions & Backups     │
│ • A-22 to A-28 : Nord UI, Settings, Themes, and Safer Framing Cap      │
│ • A-29 to A-49 : Robustness, Concurrency, Placeholders & Traceability │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Pre-Handoff Production Checklist

Before certifying the implementation as ready for production pipeline handoff, every gate below must be verified green:

- [ ] **1. Clean Startup & Port Resolution:**
  - App starts with default port `9013`.
  - Setting `H3_PORT=9050` cleanly rebinds to `9050`.
  - Non-loopback `H3_HOST` aborts startup immediately.
  - `GET /api/health` reports `specification_version: "0.3"` and `status: "ok"`.
- [ ] **2. Database Schema & Migration Integrity:**
  - Migrations run forward-only without errors.
  - Foreign key cascades (`ON DELETE CASCADE`) verified for all child tables.
  - Pre-migration database backup copy verified in `data/backups/`.
- [ ] **3. Security & Concurrency Hardening:**
  - Requests with foreign `Host` or `Origin` headers return HTTP 403.
  - Multi-tab edits with outdated revision return HTTP 412 `precondition`.
  - Concurrent generation requests return HTTP 409 `busy`.
  - Process generation lock is released on error, cancellation, and disconnect.
- [ ] **4. Prompt Generation & Placeholder Protocol:**
  - T2VA, I2VA, FL2VA, L2VA, and REF2VA pass preflight across all modes.
  - Dialogue lines are never exposed to LLMs; native scripts match verbatim.
  - Destination cross-cut prefixes are placed immediately after the cut header for $N > 1$.
  - Fallback prose preserves all dialogue and on-screen placeholders without loss.
- [ ] **5. Atomic Export & Collision Handling:**
  - Exporter checks collision on integer numeric `NN` alone, preventing duplicate clip numbering across padded/unpadded filenames.
  - `clip-<NN>-PLATES.txt` generated with U+2014 em dashes in attach order.
  - Snapshots created in `data/backups/` and pruned to the last 5 per clip.
- [ ] **6. 100% Automated Test Pass Rate:**
  - `pytest tests/ -v` passes with 0 failures across the complete test suite.
  - All 49 acceptance criteria in `tests/ACCEPTANCE.md` confirmed passing.
- [ ] **7. Documentation Completeness:**
  - `README.md` provides complete setup, virtualenv, and Ollama instructions.
  - `USER_GUIDE.md` provides novice and advanced walkthroughs.

---

## 4. Final Handoff Sign-Off Template

When Stage 08 is fully executed and all checkpoints pass, record the sign-off in [`RESUME_CHECKPOINT.md`](file:///home/wizdroid/Applications/h3-mechanic/docs/implementation/stages/last/RESUME_CHECKPOINT.md) marking:
- **Status:** `COMPLETE - RELEASE CERTIFIED`
- **Specification Version:** `0.3 (Final Locked)`
- **Test Suite Results:** `49 / 49 Acceptance Criteria Passing`
- **Application URL:** `http://127.0.0.1:9013`
