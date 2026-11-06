/**
 * H3 Prompt Studio Main ES Module Controller (§4.1–§4.4, §5.5, §5.6)
 */

import { renderT2VAForm } from "./modes/t2va.js";
import { renderFrameModeForm } from "./modes/frame_modes.js";
import { renderREF2VAForm } from "./modes/ref2va.js";

class AppController {
  constructor() {
    this.state = {
      projects: [],
      activeProjectId: null,
      clips: [],
      activeClip: null,
      activeTab: "generator",
      activeMode: "T2VA",
      modes: [],
      settings: {},
      isGenerating: false,
      abortController: null,
      autosaveTimer: null,
    };
  }

  async init() {
    this.bindDOM();
    await this.loadSettings();
    await this.loadModes();
    await this.loadProjects();
    this.applyTheme(this.state.settings.theme || "nord-dark");
  }

  bindDOM() {
    // Top-level Navigation
    document.getElementById("tab-generator").addEventListener("click", () => this.switchTopTab("generator"));
    document.getElementById("tab-settings").addEventListener("click", () => this.switchTopTab("settings"));

    // Theme Switcher
    const themeSelect = document.getElementById("theme-select");
    themeSelect.addEventListener("change", (e) => {
      this.applyTheme(e.target.value);
      this.saveSetting("theme", e.target.value);
    });

    // Project Controls
    document.getElementById("project-select").addEventListener("change", (e) => this.selectProject(parseInt(e.target.value, 10)));
    document.getElementById("btn-new-project").addEventListener("click", () => this.promptNewProject());

    // Clip Bar Controls
    document.getElementById("clip-select").addEventListener("change", (e) => this.selectClip(parseInt(e.target.value, 10)));
    document.getElementById("btn-new-clip").addEventListener("click", () => this.createNewClip());

    document.getElementById("clip-name").addEventListener("input", (e) => this.scheduleAutosave({ name: e.target.value }));
    document.getElementById("clip-model").addEventListener("change", (e) => this.handleModelChange(e.target.value));
    
    const durSlider = document.getElementById("clip-duration");
    durSlider.addEventListener("input", (e) => {
      document.getElementById("clip-duration-val").textContent = `${e.target.value}s`;
      this.scheduleAutosave({ duration_s: parseInt(e.target.value, 10) });
    });

    document.getElementById("clip-resolution").addEventListener("change", (e) => this.scheduleAutosave({ resolution: e.target.value }));
    document.getElementById("clip-ratio").addEventListener("change", (e) => this.scheduleAutosave({ ratio: e.target.value }));

    const styleSelect = document.getElementById("clip-style");
    styleSelect.addEventListener("change", (e) => {
      const isPlain = e.target.value === "plain";
      document.getElementById("plain-style-group").style.display = isPlain ? "flex" : "none";
      this.scheduleAutosave({ style_id: e.target.value });
    });

    document.getElementById("clip-plain-style").addEventListener("change", (e) => this.scheduleAutosave({ plain_style_pair: e.target.value }));
    document.getElementById("clip-language").addEventListener("change", (e) => this.scheduleAutosave({ language: e.target.value }));
    
    document.getElementById("clip-audio-policy").addEventListener("change", (e) => {
      this.scheduleAutosave({ audio_policy: e.target.value });
      if (this.state.activeClip) {
        this.state.activeClip.audio_policy = e.target.value;
        this.renderActiveModeForm();
      }
    });

    // Generator Actions
    document.getElementById("btn-generate").addEventListener("click", () => this.generatePrompt());
    document.getElementById("btn-cancel").addEventListener("click", () => this.cancelGeneration());
    document.getElementById("btn-run-preflight").addEventListener("click", () => this.runPreflightCheck());
    document.getElementById("btn-export").addEventListener("click", () => this.exportClip());
    document.getElementById("btn-copy-prompt").addEventListener("click", () => this.copyPromptText());
    document.getElementById("btn-variation").addEventListener("click", () => this.createVariation());

    // Settings Tab Controls
    document.getElementById("btn-save-settings").addEventListener("click", () => this.saveAllSettings());
    document.getElementById("setting-drafter-model").addEventListener("change", (e) => this.loadModelInfo(e.target.value));
    document.getElementById("btn-validate-export-dir").addEventListener("click", () => this.validateExportDirectory());
  }

  // ============================================================================
  // Top-Level Tabs & Modes (§4.3)
  // ============================================================================

  switchTopTab(tabName) {
    this.state.activeTab = tabName;
    document.querySelectorAll(".top-nav .tab-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === tabName);
    });
    document.getElementById("view-generator").style.display = tabName === "generator" ? "flex" : "none";
    document.getElementById("view-settings").style.display = tabName === "settings" ? "flex" : "none";

    if (tabName === "settings") {
      this.populateSettingsView();
    }
  }

  async loadModes() {
    try {
      const res = await fetch("/api/modes");
      this.state.modes = await res.json();
      const modeBar = document.getElementById("mode-bar");
      modeBar.innerHTML = "";

      this.state.modes.forEach((m) => {
        const btn = document.createElement("button");
        btn.className = `mode-tab ${m.id === this.state.activeMode ? "active" : ""}`;
        btn.textContent = m.label;
        btn.dataset.mode = m.id;
        btn.addEventListener("click", () => this.switchMode(m.id));
        modeBar.appendChild(btn);
      });
    } catch (err) {
      console.error("Failed to load modes", err);
    }
  }

  switchMode(modeId) {
    if (this.state.activeMode === modeId) return;
    this.state.activeMode = modeId;
    document.querySelectorAll(".mode-tab").forEach((b) => {
      b.classList.toggle("active", b.dataset.mode === modeId);
    });

    document.getElementById("mode-panel-title").textContent = `${modeId} Inputs`;

    // Mode-specific ratio rules (§4.4)
    const ratioSelect = document.getElementById("clip-ratio");
    if (modeId === "T2VA") {
      ratioSelect.disabled = false;
      ratioSelect.value = "16:9";
    } else if (["I2VA", "FL2VA", "L2VA"].includes(modeId)) {
      ratioSelect.value = "adaptive";
      ratioSelect.disabled = true;
    } else if (modeId === "REF2VA") {
      ratioSelect.disabled = false;
    }

    if (this.state.activeClip) {
      const updates = { mode: modeId, ratio: ratioSelect.value };
      if (modeId === "FL2VA" && !this.state.activeClip.requested_shot_count) {
        updates.requested_shot_count = 1;
      }
      this.scheduleAutosave(updates);
    }
    this.renderActiveModeForm();
  }

  // ============================================================================
  // Project & Clip Management (§4.4.1)
  // ============================================================================

  async loadProjects() {
    try {
      const res = await fetch("/api/projects");
      this.state.projects = await res.json();

      if (this.state.projects.length === 0) {
        // Create initial default project
        const pRes = await fetch("/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: "Default Project", notes: "Initial workspace" }),
        });
        const newProj = await pRes.json();
        this.state.projects = [newProj];
      }

      const pSelect = document.getElementById("project-select");
      pSelect.innerHTML = "";
      this.state.projects.forEach((p) => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        pSelect.appendChild(opt);
      });

      const initialProjId = this.state.projects[0].id;
      pSelect.value = initialProjId;
      await this.selectProject(initialProjId);
    } catch (err) {
      console.error("Failed to load projects", err);
    }
  }

  async promptNewProject() {
    const name = prompt("Enter new project name:");
    if (!name || !name.trim()) return;
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) {
        alert("Failed to create project (name may already exist)");
        return;
      }
      const proj = await res.json();
      this.state.projects.unshift(proj);
      const pSelect = document.getElementById("project-select");
      const opt = document.createElement("option");
      opt.value = proj.id;
      opt.textContent = proj.name;
      pSelect.insertBefore(opt, pSelect.firstChild);
      pSelect.value = proj.id;
      await this.selectProject(proj.id);
    } catch (err) {
      console.error(err);
    }
  }

  async selectProject(projectId) {
    this.state.activeProjectId = projectId;
    try {
      const res = await fetch(`/api/projects/${projectId}/clips`);
      this.state.clips = await res.json();

      if (this.state.clips.length === 0) {
        await this.createNewClip();
        return;
      }

      this.populateClipSelect();
      await this.selectClip(this.state.clips[0].id);
    } catch (err) {
      console.error("Failed to select project", err);
    }
  }

  async createNewClip() {
    if (!this.state.activeProjectId) return;
    try {
      const res = await fetch(`/api/projects/${this.state.activeProjectId}/clips`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: this.state.activeMode,
          h3_model: "MiniMax-H3",
          duration_s: 8,
          resolution: "768P",
          ratio: this.state.activeMode === "T2VA" ? "16:9" : "adaptive",
          audio_policy: "dialogue_only",
          requested_shot_count: this.state.activeMode === "FL2VA" ? 1 : null,
        }),
      });
      const newClip = await res.json();
      this.state.clips.unshift(newClip);
      this.populateClipSelect();
      await this.selectClip(newClip.id);
    } catch (err) {
      console.error("Failed to create clip", err);
    }
  }

  populateClipSelect() {
    const cSelect = document.getElementById("clip-select");
    cSelect.innerHTML = "";
    this.state.clips.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.name} (${c.mode})`;
      cSelect.appendChild(opt);
    });
  }

  async selectClip(clipId) {
    try {
      const res = await fetch(`/api/clips/${clipId}`);
      if (!res.ok) return;
      const clip = await res.json();
      this.state.activeClip = clip;
      this.state.activeMode = clip.mode || "T2VA";

      // Sync Mode Tabs UI
      document.querySelectorAll(".mode-tab").forEach((b) => {
        b.classList.toggle("active", b.dataset.mode === this.state.activeMode);
      });
      document.getElementById("mode-panel-title").textContent = `${this.state.activeMode} Inputs`;

      // Sync Clip Bar Inputs
      document.getElementById("clip-select").value = clip.id;
      document.getElementById("clip-name").value = clip.name || "";
      document.getElementById("clip-model").value = clip.h3_model || "MiniMax-H3";

      this.updateModelConstraints(clip.h3_model || "MiniMax-H3");

      document.getElementById("clip-duration").value = clip.duration_s || 8;
      document.getElementById("clip-duration-val").textContent = `${clip.duration_s || 8}s`;
      document.getElementById("clip-resolution").value = clip.resolution || "768P";
      document.getElementById("clip-ratio").value = clip.ratio || "16:9";
      document.getElementById("clip-ratio").disabled = ["I2VA", "FL2VA", "L2VA"].includes(this.state.activeMode);

      document.getElementById("clip-style").value = clip.style_id || "plain";
      const isPlain = (clip.style_id || "plain") === "plain";
      document.getElementById("plain-style-group").style.display = isPlain ? "flex" : "none";
      document.getElementById("clip-plain-style").value = clip.plain_style_pair || "Live-action, cinematic";

      document.getElementById("clip-language").value = clip.language || "English";
      document.getElementById("clip-audio-policy").value = clip.audio_policy || "dialogue_only";

      // Render Dynamic Form
      this.renderActiveModeForm();

      // Render Prompt & Preflight
      this.renderPromptOutput(clip.selected_prompt);
      this.runPreflightCheck();
    } catch (err) {
      console.error("Failed to select clip", err);
    }
  }

  renderActiveModeForm() {
    const container = document.getElementById("mode-form-container");
    if (!this.state.activeClip) return;

    if (this.state.activeMode === "T2VA") {
      renderT2VAForm(container, this.state.activeClip, (updates) => this.scheduleAutosave(updates));
    } else if (["I2VA", "FL2VA", "L2VA"].includes(this.state.activeMode)) {
      renderFrameModeForm(container, this.state.activeClip, (updates) => this.scheduleAutosave(updates));
    } else if (this.state.activeMode === "REF2VA") {
      renderREF2VAForm(container, this.state.activeClip, (updates) => this.scheduleAutosave(updates));
    } else {
      container.innerHTML = `
        <div style="padding: 1.5rem; text-align: center; color: var(--text-secondary); background-color: var(--bg-elevated); border-radius: 6px;">
          <h4 style="color: var(--accent); margin-bottom: 0.5rem;">${this.state.activeMode} Mode Module</h4>
          <p style="font-size: 0.85rem;">This mode module will be activated in upcoming development stages (Stage 07).</p>
        </div>
      `;
    }
  }

  // ============================================================================
  // Model Constraints (§4.4.1)
  // ============================================================================

  handleModelChange(modelName) {
    this.updateModelConstraints(modelName);
    this.scheduleAutosave({
      h3_model: modelName,
      duration_s: parseInt(document.getElementById("clip-duration").value, 10),
      resolution: document.getElementById("clip-resolution").value,
    });
  }

  updateModelConstraints(modelName) {
    const durSlider = document.getElementById("clip-duration");
    const resSelect = document.getElementById("clip-resolution");

    if (modelName === "MiniMax-H3-Max") {
      durSlider.min = 5;
      if (parseInt(durSlider.value, 10) < 5) durSlider.value = 5;
      resSelect.innerHTML = `
        <option value="480P">480P</option>
        <option value="768P">768P</option>
      `;
    } else {
      durSlider.min = 4;
      resSelect.innerHTML = `
        <option value="768P">768P</option>
        <option value="2K">2K</option>
      `;
    }
    document.getElementById("clip-duration-val").textContent = `${durSlider.value}s`;
  }

  // ============================================================================
  // Debounced Autosave with Optimistic Locking (§5.7)
  // ============================================================================

  scheduleAutosave(updates) {
    if (!this.state.activeClip) return;
    Object.assign(this.state.activeClip, updates);

    const indicator = document.getElementById("autosave-indicator");
    indicator.textContent = "Saving...";
    indicator.className = "badge badge-saving";

    clearTimeout(this.state.autosaveTimer);
    this.state.autosaveTimer = setTimeout(() => this.executeAutosave(updates), 500);
  }

  async executeAutosave(updates) {
    if (!this.state.activeClip) return;
    const clipId = this.state.activeClip.id;
    const rev = this.state.activeClip.revision;

    try {
      const res = await fetch(`/api/clips/${clipId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "If-Match": `"${rev}"`,
        },
        body: JSON.stringify(updates),
      });

      const indicator = document.getElementById("autosave-indicator");
      if (res.status === 412) {
        indicator.textContent = "Conflict";
        indicator.className = "badge badge-conflict";
        return;
      }

      if (res.ok) {
        const updated = await res.json();
        this.state.activeClip = updated;
        indicator.textContent = "Saved";
        indicator.className = "badge badge-saved";

        // If inputs changed, check if stale banner should appear
        if (updated.selected_prompt && updated.inputs_revision !== updated.selected_prompt.inputs_revision) {
          document.getElementById("stale-banner").style.display = "flex";
        } else {
          document.getElementById("stale-banner").style.display = "none";
        }
      }
    } catch (err) {
      console.error("Autosave failed", err);
    }
  }

  // ============================================================================
  // Streaming Generation Pipeline (§5.5, §5.6)
  // ============================================================================

  async generatePrompt() {
    if (!this.state.activeClip || this.state.isGenerating) return;

    this.state.isGenerating = true;
    this.state.abortController = new AbortController();

    // Toggle Action Buttons
    document.getElementById("btn-generate").style.display = "none";
    document.getElementById("btn-cancel").style.display = "inline-flex";
    document.getElementById("progress-strip").style.display = "flex";

    this.resetProgressStrip();
    const clipId = this.state.activeClip.id;
    const drafter = this.state.settings.drafter_model || "qwen2.5:7b-instruct";

    try {
      const response = await fetch(`/api/clips/${clipId}/generate`, {
        method: "POST",
        headers: {
          "Accept": "application/x-ndjson",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ drafter_model: drafter }),
        signal: this.state.abortController.signal,
      });

      if (response.status === 422) {
        const errData = await response.json();
        alert(`Stage 0 Validation Error:\n${errData.detail?.error?.message || "Invalid inputs"}`);
        this.finishGeneration();
        return;
      }

      if (response.status === 409) {
        const errData = await response.json();
        alert(`Engine Busy: ${errData.detail?.error?.message || "Generation in flight"}`);
        this.finishGeneration();
        return;
      }

      if (!response.ok) {
        alert(`Generation request failed: HTTP ${response.status}`);
        this.finishGeneration();
        return;
      }

      // Stream NDJSON Progress Lines
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep remainder

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line.trim());
            this.handlePipelineEvent(event);
          } catch (e) {
            console.warn("Could not parse NDJSON line:", line);
          }
        }
      }

      // Reload clip to get freshly saved prompt
      await this.selectClip(clipId);
    } catch (err) {
      if (err.name !== "AbortError") {
        console.error("Pipeline streaming failed", err);
      }
    } finally {
      this.finishGeneration();
    }
  }

  handlePipelineEvent(event) {
    const elapsedEl = document.getElementById("generation-elapsed");
    if (event.ms) {
      elapsedEl.textContent = `${event.ms}ms`;
    }

    if (event.event === "stage_start") {
      this.setStageStatus(event.stage, "active");
    } else if (event.event === "stage_done") {
      this.setStageStatus(event.stage, "done");
    } else if (event.event === "stage_retry") {
      this.setStageStatus(event.stage, "retry");
    } else if (event.event === "violations") {
      this.renderChecklistResults(event.violations || []);
    } else if (event.event === "error") {
      alert(`Pipeline Error: ${event.error?.message || "Unknown error"}`);
    }
  }

  setStageStatus(stageName, statusClass) {
    const stageMap = {
      seed_elaboration: "stage-seed",
      prose_writer: "stage-prose",
      preflight_fixer: "stage-fix",
    };
    const pillId = stageMap[stageName];
    if (pillId) {
      const pill = document.getElementById(pillId);
      if (pill) {
        pill.style.display = "inline-block";
        pill.className = `stage-pill ${statusClass}`;
      }
    }
  }

  resetProgressStrip() {
    ["stage-seed", "stage-prose", "stage-render", "stage-preflight", "stage-fix"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.className = "stage-pill";
    });
    document.getElementById("stage-fix").style.display = "none";
  }

  async cancelGeneration() {
    if (!this.state.activeClip) return;
    if (this.state.abortController) {
      this.state.abortController.abort();
    }
    await fetch(`/api/clips/${this.state.activeClip.id}/generate/cancel`, { method: "POST" });
    this.finishGeneration();
  }

  finishGeneration() {
    this.state.isGenerating = false;
    document.getElementById("btn-generate").style.display = "inline-flex";
    document.getElementById("btn-cancel").style.display = "none";
  }

  // ============================================================================
  // Prompt Output & Syntax Highlighting (§4.1)
  // ============================================================================

  renderPromptOutput(promptObj) {
    const previewEl = document.getElementById("prompt-preview");
    const statusBadge = document.getElementById("prompt-status-badge");
    const staleBanner = document.getElementById("stale-banner");
    const fallbackBanner = document.getElementById("fallback-banner");
    const charCounter = document.getElementById("char-counter");
    const wordCounter = document.getElementById("word-counter");

    if (!promptObj) {
      previewEl.textContent = "";
      statusBadge.textContent = "DRAFT";
      statusBadge.className = "badge";
      staleBanner.style.display = "none";
      fallbackBanner.style.display = "none";
      charCounter.textContent = "0 / 7000";
      wordCounter.textContent = "0";
      return;
    }

    const raw = promptObj.body || "";
    previewEl.innerHTML = this.highlightPromptSyntax(raw);

    // Update Status Badge
    const status = promptObj.stage || this.state.activeClip?.status || "DRAFT";
    statusBadge.textContent = status.toUpperCase();
    statusBadge.className = `badge ${status === "preflight" ? "badge-saved" : (status === "blocked" ? "badge-conflict" : "badge-version")}`;

    // Stale Banner (§4.2)
    const isStale = this.state.activeClip && promptObj.inputs_revision !== this.state.activeClip.inputs_revision;
    staleBanner.style.display = isStale ? "flex" : "none";

    // Fallback Prose Banner (§8.1b)
    fallbackBanner.style.display = promptObj.prose_fallback ? "flex" : "none";

    // Unicode Code Point Character Counter (§4.2, §10.1)
    const codePointCount = [...raw].length;
    charCounter.textContent = `${codePointCount} / 7000`;
    charCounter.className = `char-count ${codePointCount <= 7000 ? "valid" : "overflow"}`;

    // Word Counter
    const words = raw.trim().split(/\s+/).filter(Boolean).length;
    wordCounter.textContent = words.toString();
  }

  highlightPromptSyntax(text) {
    if (!text) return "";
    let safe = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Highlight Section Headers
    safe = safe.replace(/(integrated_multimodal_description:|overall_soundscape:|non_diegetic_music:|subject_definitions:|summary:|retention_analysis:|detailed_description:)/g, '<span class="hl-header">$1</span>');

    // Highlight Shots [Shot N]
    safe = safe.replace(/(\[Shot \d+\])/g, '<span class="hl-shot">$1</span>');

    // Highlight Dialogue <d>...</d>
    safe = safe.replace(/(&lt;d&gt;.*?&lt;\/d&gt;)/g, '<span class="hl-dialogue">$1</span>');

    // Highlight Special Tags
    safe = safe.replace(/(&lt;scenetrans&gt;|&lt;cutoff&gt;|&lt;Picture \d+&gt;|&lt;Subject \d+&gt;|&lt;Audio \d+&gt;)/g, '<span class="hl-tag">$1</span>');

    return safe;
  }

  copyPromptText() {
    const raw = this.state.activeClip?.selected_prompt?.body || document.getElementById("prompt-preview").innerText;
    if (!raw) return;
    navigator.clipboard.writeText(raw).then(() => alert("Prompt copied to clipboard!"));
  }

  // ============================================================================
  // Preflight Checklist Runner (§5.4, §9)
  // ============================================================================

  async runPreflightCheck() {
    if (!this.state.activeClip) return;
    try {
      const res = await fetch(`/api/clips/${this.state.activeClip.id}/preflight`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_autofix: false }),
      });
      if (res.ok) {
        const violations = await res.json();
        this.renderChecklistResults(violations);
      }
    } catch (err) {
      console.error("Preflight check failed", err);
    }
  }

  renderChecklistResults(violations) {
    const listEl = document.getElementById("checklist-results");
    const summaryEl = document.getElementById("checklist-summary");

    listEl.innerHTML = "";
    if (violations.length === 0) {
      summaryEl.textContent = "All Passing";
      listEl.innerHTML = `
        <div class="rule-item pass">
          <div class="rule-header">
            <span>✓ Preflight Passed</span>
            <span class="badge badge-saved">100% OK</span>
          </div>
          <div class="rule-message">Prompt conforms strictly to all H3 validation criteria. Ready for export.</div>
        </div>
      `;
      return;
    }

    const errors = violations.filter((v) => v.blocking);
    const warnings = violations.filter((v) => !v.blocking);
    summaryEl.textContent = `${errors.length} Errors · ${warnings.length} Warnings`;

    violations.forEach((v) => {
      const item = document.createElement("div");
      item.className = `rule-item ${v.blocking ? "error" : "warning"}`;
      item.innerHTML = `
        <div class="rule-header">
          <strong>${v.rule_id}: ${v.section}</strong>
          <span class="badge ${v.blocking ? "badge-conflict" : "badge-saving"}">${v.severity}</span>
        </div>
        <div class="rule-message">${v.message}</div>
      `;
      listEl.appendChild(item);
    });
  }

  // ============================================================================
  // Export & Variations (§5.5, §10)
  // ============================================================================

  async exportClip() {
    if (!this.state.activeClip) return;
    try {
      const res = await fetch(`/api/clips/${this.state.activeClip.id}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ overwrite: false }),
      });
      if (res.status === 409) {
        const confirmOverwrite = confirm("Export collision detected. Overwrite existing clip file?");
        if (confirmOverwrite) {
          const res2 = await fetch(`/api/clips/${this.state.activeClip.id}/export`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ overwrite: true }),
          });
          const data2 = await res2.json();
          alert(`Successfully exported:\n${data2.filename}`);
        }
        return;
      }
      if (res.ok) {
        const data = await res.json();
        alert(`Successfully exported:\n${data.filename}`);
      } else {
        alert("Export failed. Make sure prompt has no blocking errors.");
      }
    } catch (err) {
      console.error("Export failed", err);
    }
  }

  async createVariation() {
    if (!this.state.activeClip) return;
    try {
      const res = await fetch(`/api/clips/${this.state.activeClip.id}/variations`, { method: "POST" });
      if (res.status === 409) {
        alert("A safer framing variation already exists for this draft.");
        return;
      }
      if (res.ok) {
        alert("Variation created. Refreshing clip view.");
        await this.selectClip(this.state.activeClip.id);
      }
    } catch (err) {
      console.error("Variation failed", err);
    }
  }

  // ============================================================================
  // Settings & Theme (§4.4.7, §7.5)
  // ============================================================================

  async loadSettings() {
    try {
      const res = await fetch("/api/settings");
      this.state.settings = await res.json();
    } catch (err) {
      console.error("Failed to load settings", err);
    }
  }

  async saveSetting(key, value) {
    this.state.settings[key] = value;
    await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [key]: value }),
    });
  }

  applyTheme(themeName) {
    document.body.className = themeName;
    document.getElementById("theme-select").value = themeName;
  }

  async populateSettingsView() {
    const s = this.state.settings;
    document.getElementById("setting-endpoint").value = s.ollama_endpoint || "http://127.0.0.1:11434";
    document.getElementById("setting-temperature").value = s.temperature || 0.2;
    document.getElementById("setting-num-ctx").value = s.num_ctx || 8192;
    document.getElementById("setting-timeout").value = s.timeout_s || 120;
    document.getElementById("setting-max-retries").value = s.max_fixer_retries || 2;
    document.getElementById("setting-export-dir").value = s.export_directory || "";
    document.getElementById("setting-collision").value = s.collision_policy || "auto_increment";
    document.getElementById("setting-listen-port").value = s.listen_port || 9013;

    // Load Models for Drafter dropdown
    await this.loadDrafterModels();

    // Load Voice Library
    await this.loadVoiceLibrary();
  }

  async loadDrafterModels() {
    const modelSelect = document.getElementById("setting-drafter-model");
    modelSelect.innerHTML = `<option value="">Loading models...</option>`;
    try {
      const res = await fetch("/api/models");
      const models = await res.json();
      modelSelect.innerHTML = "";

      if (models.length === 0) {
        modelSelect.innerHTML = `<option value="qwen2.5:7b-instruct">qwen2.5:7b-instruct (default)</option>`;
      } else {
        models.forEach((m) => {
          const opt = document.createElement("option");
          opt.value = m.name;
          opt.textContent = m.name;
          if (m.name === (this.state.settings.drafter_model || "qwen2.5:7b-instruct")) {
            opt.selected = true;
          }
          modelSelect.appendChild(opt);
        });
      }
      this.loadModelInfo(modelSelect.value);
    } catch (err) {
      modelSelect.innerHTML = `<option value="qwen2.5:7b-instruct">qwen2.5:7b-instruct (offline)</option>`;
    }
  }

  async loadModelInfo(modelName) {
    if (!modelName) return;
    const infoBox = document.getElementById("model-info-box");
    const infoText = document.getElementById("model-info-text");
    try {
      const res = await fetch(`/api/models/${encodeURIComponent(modelName)}`);
      if (res.ok) {
        const info = await res.json();
        infoBox.style.display = "block";
        const fam = info.details?.family || "unknown";
        const param = info.details?.parameter_size || "unknown";
        const quant = info.details?.quantization_level || "unknown";
        infoText.textContent = `Family: ${fam} · Parameters: ${param} · Quantization: ${quant}`;
      } else {
        infoBox.style.display = "none";
      }
    } catch (err) {
      infoBox.style.display = "none";
    }
  }

  async loadVoiceLibrary() {
    const tbody = document.getElementById("voice-table-body");
    try {
      const res = await fetch("/api/voices");
      const voices = await res.json();
      tbody.innerHTML = "";

      Object.entries(voices).forEach(([vid, data]) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${vid}</strong></td>
          <td>${data.name}</td>
          <td>${data.roles}</td>
          <td style="font-style: italic; color: var(--text-secondary);">${data.paste_phrase}</td>
        `;
        tbody.appendChild(tr);
      });
    } catch (err) {
      console.error("Failed to load voices", err);
    }
  }

  async saveAllSettings() {
    const updates = {
      ollama_endpoint: document.getElementById("setting-endpoint").value.trim(),
      drafter_model: document.getElementById("setting-drafter-model").value,
      temperature: parseFloat(document.getElementById("setting-temperature").value),
      num_ctx: parseInt(document.getElementById("setting-num-ctx").value, 10),
      timeout_s: parseInt(document.getElementById("setting-timeout").value, 10),
      max_fixer_retries: parseInt(document.getElementById("setting-max-retries").value, 10),
      export_directory: document.getElementById("setting-export-dir").value.trim(),
      collision_policy: document.getElementById("setting-collision").value,
      listen_port: parseInt(document.getElementById("setting-listen-port").value, 10),
    };
    await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    alert("Settings saved successfully!");
  }

  async validateExportDirectory() {
    const dir = document.getElementById("setting-export-dir").value.trim();
    const feedback = document.getElementById("export-dir-feedback");
    feedback.textContent = "Validating...";
    feedback.style.color = "var(--text-muted)";

    // Simple test validation call
    if (dir.startsWith("/")) {
      feedback.textContent = "✓ Valid absolute path";
      feedback.style.color = "var(--nord14)";
    } else {
      feedback.textContent = "✗ Must be an absolute filesystem path";
      feedback.style.color = "var(--nord11)";
    }
  }
}

// Instantiate and initialize on DOM ready
document.addEventListener("DOMContentLoaded", () => {
  const app = new AppController();
  app.init();
});
