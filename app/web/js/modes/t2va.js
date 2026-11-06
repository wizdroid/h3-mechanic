/**
 * T2VA Mode View Component (§4.4.2, §7.2)
 *
 * Inputs:
 * - Seed text (free text, >= 1 sentence)
 * - Draft manually checkbox & manual template textarea
 * - Dialogue lines table (speaker, language, delivery, native-script text, gloss, voiceover, cutoff)
 * - Custom soundscape and non-diegetic music fields (when audio_policy == 'custom')
 */

export function renderT2VAForm(container, clip, onUpdate) {
  container.innerHTML = "";

  const formWrapper = document.createElement("div");
  formWrapper.style.display = "flex";
  formWrapper.style.flexDirection = "column";
  formWrapper.style.gap = "0.9rem";

  // 1. Seed Text Area
  const seedGroup = document.createElement("div");
  seedGroup.className = "form-group";
  seedGroup.innerHTML = `
    <label for="t2va-seed-text"><strong>Seed Text</strong> (free text, description of setting, mood, and actions):</label>
    <textarea id="t2va-seed-text" rows="3" placeholder="A detective walks into an abandoned warehouse in the rain...">${clip.seed_text || ""}</textarea>
  `;
  const seedTextarea = seedGroup.querySelector("#t2va-seed-text");
  seedTextarea.addEventListener("input", (e) => {
    onUpdate({ seed_text: e.target.value });
  });
  formWrapper.appendChild(seedGroup);

  // 2. Manual Draft Checkbox & Template (§4.4.2)
  const manualGroup = document.createElement("div");
  manualGroup.className = "form-group";
  manualGroup.innerHTML = `
    <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
      <input type="checkbox" id="t2va-manual-draft" ${clip.manual_draft ? "checked" : ""}>
      <span><strong>Draft Manually</strong> (skip Ollama stages; run renderer & preflight directly)</span>
    </label>
    <div id="manual-template-container" style="display: ${clip.manual_draft ? "block" : "none"}; margin-top: 0.5rem;">
      <textarea id="t2va-manual-template" rows="4" placeholder="[Shot 1] Live-action, cinematic. The detective steps inside. {{L1}}">${clip.manual_template || ""}</textarea>
    </div>
  `;
  const manualCheckbox = manualGroup.querySelector("#t2va-manual-draft");
  const manualTemplateBox = manualGroup.querySelector("#manual-template-container");
  const manualTextarea = manualGroup.querySelector("#t2va-manual-template");

  manualCheckbox.addEventListener("change", (e) => {
    const isManual = e.target.checked ? 1 : 0;
    manualTemplateBox.style.display = isManual ? "block" : "none";
    onUpdate({ manual_draft: isManual });
  });

  manualTextarea.addEventListener("input", (e) => {
    onUpdate({ manual_template: e.target.value });
  });
  formWrapper.appendChild(manualGroup);

  // 3. Custom Audio Textareas (visible when audio_policy == 'custom')
  if (clip.audio_policy === "custom") {
    const audioGroup = document.createElement("div");
    audioGroup.className = "form-group";
    audioGroup.innerHTML = `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
        <div>
          <label for="t2va-soundscape"><strong>Soundscape</strong> (1–4 sentences):</label>
          <textarea id="t2va-soundscape" rows="2" placeholder="Heavy rain drums rhythmically against the corrugated iron roof.">${clip.custom_soundscape || ""}</textarea>
        </div>
        <div>
          <label for="t2va-music"><strong>Non-diegetic Music</strong> (1–3 sentences or N/A):</label>
          <textarea id="t2va-music" rows="2" placeholder="A low melancholic cello melody rises quietly in the background.">${clip.custom_music || ""}</textarea>
        </div>
      </div>
    `;
    const soundscapeArea = audioGroup.querySelector("#t2va-soundscape");
    const musicArea = audioGroup.querySelector("#t2va-music");
    soundscapeArea.addEventListener("input", (e) => onUpdate({ custom_soundscape: e.target.value }));
    musicArea.addEventListener("input", (e) => onUpdate({ custom_music: e.target.value }));
    formWrapper.appendChild(audioGroup);
  }

  // 4. Dialogue Lines Table Section (§4.4.2)
  renderDialogueLinesSection(formWrapper, clip, onUpdate);
  container.appendChild(formWrapper);
}

export function renderDialogueLinesSection(parentContainer, clip, onUpdate) {
  const linesSection = document.createElement("div");
  linesSection.className = "form-group";
  linesSection.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
      <label><strong>Dialogue Lines (Optional Rows)</strong></label>
      <button id="btn-add-line" class="btn" style="font-size: 0.78rem; padding: 0.2rem 0.5rem;">+ Add Line</button>
    </div>
    <div style="max-height: 220px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 5px;">
      <table class="dialogue-table">
        <thead>
          <tr>
            <th style="width: 30px;">#</th>
            <th style="width: 90px;">Language</th>
            <th style="width: 90px;">Delivery</th>
            <th>Native Script Text</th>
            <th style="width: 100px;">Gloss</th>
            <th style="width: 40px;" title="Voiceover">VO</th>
            <th style="width: 40px;" title="Cutoff">Cut</th>
            <th style="width: 30px;"></th>
          </tr>
        </thead>
        <tbody id="dialogue-lines-tbody"></tbody>
      </table>
    </div>
  `;

  parentContainer.appendChild(linesSection);
  const tbody = linesSection.querySelector("#dialogue-lines-tbody");
  loadDialogueLines(clip.id, tbody, onUpdate);

  const addLineBtn = linesSection.querySelector("#btn-add-line");
  addLineBtn.addEventListener("click", async () => {
    await fetch(`/api/clips/${clip.id}/lines`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: clip.language || "English",
        text_raw: clip.language === "Kannada" ? "ಬೇಗ ಬಾ, ಸಮಯವಿಲ್ಲ!" : "Stop right there!",
        delivery: "none",
        gloss: "",
        voiceover: 0,
        cutoff: 0,
      }),
    });
    loadDialogueLines(clip.id, tbody, onUpdate);
  });
}

export async function loadDialogueLines(clipId, tbody, onUpdate) {
  try {
    const res = await fetch(`/api/clips/${clipId}/lines`);
    if (!res.ok) return;
    const lines = await res.json();
    tbody.innerHTML = "";

    if (lines.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 0.6rem;">No dialogue lines attached. Click '+ Add Line' to add one.</td></tr>`;
      return;
    }

    lines.forEach((line, idx) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight: 700; color: var(--accent);">${idx + 1}</td>
        <td>
          <select class="line-lang" style="padding: 0.2rem; font-size: 0.78rem; width: 100%;">
            ${["English", "Kannada", "Hindi", "Marathi", "Tamil", "Telugu", "Malayalam", "Bengali"]
              .map((l) => `<option value="${l}" ${l === line.language ? "selected" : ""}>${l}</option>`)
              .join("")}
          </select>
        </td>
        <td>
          <select class="line-delivery" style="padding: 0.2rem; font-size: 0.78rem; width: 100%;">
            ${["none", "whisper", "shout", "command", "mumble", "sob", "choked", "plead", "sarcastic", "tender", "menacing", "cold", "deadpan"]
              .map((d) => `<option value="${d}" ${d === line.delivery ? "selected" : ""}>${d}</option>`)
              .join("")}
          </select>
        </td>
        <td>
          <input type="text" class="line-text" value="${line.text_raw.replace(/"/g, "&quot;")}" style="padding: 0.2rem 0.4rem; font-size: 0.8rem; width: 100%;">
        </td>
        <td>
          <input type="text" class="line-gloss" value="${(line.gloss || "").replace(/"/g, "&quot;")}" placeholder="optional" style="padding: 0.2rem 0.4rem; font-size: 0.78rem; width: 100%;">
        </td>
        <td style="text-align: center;">
          <input type="checkbox" class="line-vo" ${line.voiceover ? "checked" : ""}>
        </td>
        <td style="text-align: center;">
          <input type="checkbox" class="line-cut" ${line.cutoff ? "checked" : ""}>
        </td>
        <td style="text-align: center;">
          <button class="btn btn-sm btn-del-line" title="Delete line" style="padding: 0.1rem 0.35rem; font-size: 0.75rem; color: var(--nord11);">×</button>
        </td>
      `;

      // Event listeners for line update
      const updateLine = async (fieldUpdates) => {
        await fetch(`/api/lines/${line.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(fieldUpdates),
        });
        if (onUpdate) onUpdate({});
      };

      tr.querySelector(".line-lang").addEventListener("change", (e) => updateLine({ language: e.target.value }));
      tr.querySelector(".line-delivery").addEventListener("change", (e) => updateLine({ delivery: e.target.value }));
      tr.querySelector(".line-text").addEventListener("change", (e) => updateLine({ text_raw: e.target.value }));
      tr.querySelector(".line-gloss").addEventListener("change", (e) => updateLine({ gloss: e.target.value }));
      tr.querySelector(".line-vo").addEventListener("change", (e) => updateLine({ voiceover: e.target.checked ? 1 : 0 }));
      tr.querySelector(".line-cut").addEventListener("change", (e) => updateLine({ cutoff: e.target.checked ? 1 : 0 }));
      tr.querySelector(".btn-del-line").addEventListener("click", async () => {
        await fetch(`/api/lines/${line.id}`, { method: "DELETE" });
        loadDialogueLines(clipId, tbody, onUpdate);
      });

      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to load dialogue lines", err);
  }
}
