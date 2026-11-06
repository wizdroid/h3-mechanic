/**
 * Frame Modes View Component (I2VA, FL2VA, L2VA) (§4.4.3–§4.4.5, §7.3, §7.6, Appendix A.2)
 *
 * Inputs:
 * - Frame token cards:
 *   * I2VA: exactly 1 frame reference (<Picture 1>, first_frame)
 *   * FL2VA: exactly 2 frame references (<Picture 1> first_frame, <Picture 2> last_frame)
 *   * L2VA: exactly 1 frame reference (<Picture 1>, last_frame)
 * - Action / Transition text (motion sequence or evolution between frames)
 * - Shots control (defaults to 1 for FL2VA waiving PF-03 minimum; 1-5 for I2VA/L2VA)
 * - Read-only instruction line preview (computed by code per Appendix A.2)
 * - Dialogue lines table & custom audio fields
 */

import { renderDialogueLinesSection } from "./t2va.js";

export async function renderFrameModeForm(container, clip, onUpdate) {
  container.innerHTML = "";

  const formWrapper = document.createElement("div");
  formWrapper.style.display = "flex";
  formWrapper.style.flexDirection = "column";
  formWrapper.style.gap = "0.9rem";

  const mode = clip.mode || "I2VA";

  // 1. Mode Description Banner
  const descMap = {
    I2VA: "Image-to-Video-Audio: Single initial frame reference (&lt;Picture 1&gt;) anchoring the opening of Shot 1. Ratio locked to adaptive.",
    FL2VA: "First-Last-Frame-to-Video-Audio: Sequence begins on &lt;Picture 1&gt; and ends on &lt;Picture 2&gt;. Defaults to 1 shot. Ratio locked to adaptive.",
    L2VA: "Last-Frame-to-Video-Audio: Plausible preceding action sequence culminating and concluding on &lt;Picture 1&gt;. Ratio locked to adaptive.",
  };

  const banner = document.createElement("div");
  banner.style.padding = "0.5rem 0.8rem";
  banner.style.background = "var(--bg-elevated)";
  banner.style.borderLeft = "3px solid var(--accent)";
  banner.style.borderRadius = "4px";
  banner.style.fontSize = "0.82rem";
  banner.style.color = "var(--text-secondary)";
  banner.innerHTML = `<strong>${mode}</strong>: ${descMap[mode] || ""}`;
  formWrapper.appendChild(banner);

  // 2. Frame Tokens Section
  const framesSection = document.createElement("div");
  framesSection.className = "form-group";
  framesSection.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
      <label><strong>Frame Token Reference(s)</strong> (Images only; ratio locked to adaptive)</label>
      <span class="badge" style="background: var(--bg-surface); color: var(--accent); border: 1px solid var(--border-color);">
        ${mode === "FL2VA" ? "2 Frames Required" : "1 Frame Required"}
      </span>
    </div>
    <div id="frame-cards-container" style="display: flex; flex-direction: column; gap: 0.6rem;">
      <div style="color: var(--text-muted); font-size: 0.8rem;">Loading frame references...</div>
    </div>
  `;
  formWrapper.appendChild(framesSection);

  // 3. Action / Transition Text Area
  const isTransition = mode === "FL2VA";
  const actionLabel = isTransition ? "Transition Input" : "Action Input";
  const actionHelp = isTransition
    ? "Describe the physical motion and evolution between Picture 1 and Picture 2:"
    : (mode === "I2VA"
      ? "Describe the action sequence unfolding from the initial frame:"
      : "Describe the action sequence leading up to and concluding on the target final frame:");
  const actionPlaceholder = isTransition
    ? "the officer unlocks and swings the cell door open, stepping aside as sunlight enters..."
    : (mode === "I2VA"
      ? "she stares at her hands, then looks up and whispers a line..."
      : "she crosses the cell and settles beneath the window in the morning light...");

  const actionGroup = document.createElement("div");
  actionGroup.className = "form-group";
  actionGroup.innerHTML = `
    <label for="frame-action-text"><strong>${actionLabel}</strong> (${actionHelp})</label>
    <textarea id="frame-action-text" rows="3" placeholder="${actionPlaceholder}">${clip.action_text || ""}</textarea>
  `;
  const actionTextarea = actionGroup.querySelector("#frame-action-text");
  actionTextarea.addEventListener("input", (e) => {
    onUpdate({ action_text: e.target.value });
  });
  formWrapper.appendChild(actionGroup);

  // 4. Requested Shot Count
  const shotCountGroup = document.createElement("div");
  shotCountGroup.className = "form-group";
  const defaultShots = mode === "FL2VA" ? 1 : 2;
  const currentShots = clip.requested_shot_count || defaultShots;

  shotCountGroup.innerHTML = `
    <div style="display: flex; align-items: center; gap: 1rem;">
      <div style="display: flex; align-items: center; gap: 0.5rem;">
        <label for="frame-shot-count" style="margin-bottom: 0;"><strong>Planned Shots:</strong></label>
        <select id="frame-shot-count" style="padding: 0.25rem 0.5rem; font-size: 0.85rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
          <option value="1" ${currentShots === 1 ? "selected" : ""}>1 Shot ${mode === "FL2VA" ? "(Default - Waives PF-03 minimum)" : ""}</option>
          <option value="2" ${currentShots === 2 ? "selected" : ""}>2 Shots</option>
          <option value="3" ${currentShots === 3 ? "selected" : ""}>3 Shots</option>
          <option value="4" ${currentShots === 4 ? "selected" : ""}>4 Shots</option>
          <option value="5" ${currentShots === 5 ? "selected" : ""}>5 Shots</option>
        </select>
      </div>
      ${mode === "FL2VA" && currentShots === 1 ? '<span class="badge" style="background: rgba(163, 190, 140, 0.2); color: var(--nord14); border: 1px solid var(--nord14);">PF-03 Single-Shot Exception Active</span>' : ""}
    </div>
  `;
  const shotSelect = shotCountGroup.querySelector("#frame-shot-count");
  shotSelect.addEventListener("change", (e) => {
    const val = parseInt(e.target.value, 10);
    onUpdate({ requested_shot_count: val });
    updateInstructionPreview(clip.id, mode, val, clip.duration_s || 8, previewBox);
  });
  formWrapper.appendChild(shotCountGroup);

  // 5. Read-only Instruction Line Preview Panel (§4.4.3–§4.4.5, Appendix A.2)
  const previewGroup = document.createElement("div");
  previewGroup.className = "form-group";
  previewGroup.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
      <label><strong>Auto-Generated Instruction Line</strong> (read-only; code-generated per Appendix A.2)</label>
      <span style="font-size: 0.72rem; color: var(--text-muted); font-style: italic;">preview; computed after planning with final shot count N</span>
    </div>
    <div id="instruction-preview-box" style="font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 0.82rem; background: var(--bg-surface); padding: 0.6rem 0.85rem; border-radius: 4px; border-left: 3px solid var(--accent); color: var(--nord8); white-space: pre-wrap; line-height: 1.4;">
      Loading instruction line preview...
    </div>
  `;
  const previewBox = previewGroup.querySelector("#instruction-preview-box");
  formWrapper.appendChild(previewGroup);

  // 6. Custom Audio Textareas (when audio_policy == 'custom')
  if (clip.audio_policy === "custom") {
    const audioGroup = document.createElement("div");
    audioGroup.className = "form-group";
    audioGroup.innerHTML = `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
        <div>
          <label for="frame-soundscape"><strong>Soundscape</strong> (1–4 sentences):</label>
          <textarea id="frame-soundscape" rows="2" placeholder="Subtle ambient room tone and soft footsteps...">${clip.custom_soundscape || ""}</textarea>
        </div>
        <div>
          <label for="frame-music"><strong>Non-diegetic Music</strong> (1–3 sentences or N/A):</label>
          <textarea id="frame-music" rows="2" placeholder="A quiet low drone building tension...">${clip.custom_music || ""}</textarea>
        </div>
      </div>
    `;
    const soundscapeArea = audioGroup.querySelector("#frame-soundscape");
    const musicArea = audioGroup.querySelector("#frame-music");
    soundscapeArea.addEventListener("input", (e) => onUpdate({ custom_soundscape: e.target.value }));
    musicArea.addEventListener("input", (e) => onUpdate({ custom_music: e.target.value }));
    formWrapper.appendChild(audioGroup);
  }

  // 7. Dialogue Lines Table Section
  renderDialogueLinesSection(formWrapper, clip, onUpdate);

  container.appendChild(formWrapper);

  // Fetch frame references and auto-populate if missing
  await syncFrameReferences(clip, mode, framesSection.querySelector("#frame-cards-container"), onUpdate);

  // Initial fetch for instruction line preview
  await updateInstructionPreview(clip.id, mode, currentShots, clip.duration_s || 8, previewBox);
}

async function syncFrameReferences(clip, mode, cardsContainer, onUpdate) {
  try {
    const res = await fetch(`/api/clips/${clip.id}/references`);
    if (!res.ok) return;
    let refs = await res.json();

    // Auto-create initial references if not present
    if (mode === "I2VA" && refs.length === 0) {
      const created = await createReference(clip.id, {
        kind: "image",
        caption: "Initial frame reference",
        role_hint: "first_frame",
        source_file: "frame_01.png",
      });
      if (created) refs = [created];
    } else if (mode === "FL2VA") {
      if (refs.length === 0) {
        const ref1 = await createReference(clip.id, {
          kind: "image",
          caption: "First frame reference",
          role_hint: "first_frame",
          source_file: "frame_01.png",
        });
        const ref2 = await createReference(clip.id, {
          kind: "image",
          caption: "Last frame reference",
          role_hint: "last_frame",
          source_file: "frame_02.png",
        });
        refs = [ref1, ref2].filter(Boolean);
      } else if (refs.length === 1) {
        const ref2 = await createReference(clip.id, {
          kind: "image",
          caption: "Last frame reference",
          role_hint: "last_frame",
          source_file: "frame_02.png",
        });
        if (ref2) refs.push(ref2);
      }
    } else if (mode === "L2VA" && refs.length === 0) {
      const created = await createReference(clip.id, {
        kind: "image",
        caption: "Target final frame reference",
        role_hint: "last_frame",
        source_file: "frame_final.png",
      });
      if (created) refs = [created];
    }

    renderFrameCards(clip.id, refs, cardsContainer, onUpdate);
  } catch (err) {
    console.error("Failed to sync frame references", err);
    cardsContainer.innerHTML = `<div style="color: var(--nord11); font-size: 0.8rem;">Error loading frame references: ${err.message}</div>`;
  }
}

async function createReference(clipId, payload) {
  try {
    const res = await fetch(`/api/clips/${clipId}/references`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) return await res.json();
  } catch (err) {
    console.error("Failed to create frame reference", err);
  }
  return null;
}

function renderFrameCards(clipId, refs, container, onUpdate) {
  container.innerHTML = "";

  if (refs.length === 0) {
    container.innerHTML = `<div style="color: var(--text-muted); font-size: 0.8rem; padding: 0.5rem; text-align: center;">No frame references attached.</div>`;
    return;
  }

  refs.forEach((ref, idx) => {
    const card = document.createElement("div");
    card.style.background = "var(--bg-surface)";
    card.style.border = "1px solid var(--border-color)";
    card.style.borderRadius = "6px";
    card.style.padding = "0.75rem";
    card.style.display = "flex";
    card.style.flexDirection = "column";
    card.style.gap = "0.5rem";

    const tokenLabel = `&lt;Picture ${ref.ordinal || idx + 1}&gt;`;
    const roleBadge = ref.role_hint === "first_frame"
      ? '<span class="badge" style="background: rgba(143, 188, 187, 0.2); color: var(--nord7); border: 1px solid var(--nord7);">First Frame</span>'
      : (ref.role_hint === "last_frame"
        ? '<span class="badge" style="background: rgba(180, 142, 173, 0.2); color: var(--nord15); border: 1px solid var(--nord15);">Last Frame</span>'
        : `<span class="badge">${ref.role_hint || "Image"}</span>`);

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <strong style="color: var(--accent); font-family: monospace; font-size: 0.9rem;">${tokenLabel}</strong>
          ${roleBadge}
        </div>
        <span style="font-size: 0.72rem; color: var(--text-muted);">Position: ${ref.position || idx + 1}</span>
      </div>

      <div style="display: grid; grid-template-columns: 2fr 1.5fr 1fr 1fr; gap: 0.5rem; align-items: center;">
        <div>
          <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 0.15rem;">Caption *</label>
          <input type="text" class="ref-caption" value="${(ref.caption || "").replace(/"/g, "&quot;")}" placeholder="Frame description" style="padding: 0.25rem 0.45rem; font-size: 0.8rem; width: 100%;">
        </div>
        <div>
          <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 0.15rem;">Source File</label>
          <input type="text" class="ref-source" value="${(ref.source_file || "").replace(/"/g, "&quot;")}" placeholder="e.g. frame_01.png" style="padding: 0.25rem 0.45rem; font-size: 0.8rem; width: 100%;">
        </div>
        <div>
          <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 0.15rem;">Width (px)</label>
          <input type="number" class="ref-w" value="${ref.width_px || ""}" placeholder="opt W" min="256" max="5760" style="padding: 0.25rem 0.45rem; font-size: 0.8rem; width: 100%;">
        </div>
        <div>
          <label style="font-size: 0.72rem; color: var(--text-muted); display: block; margin-bottom: 0.15rem;">Height (px)</label>
          <input type="number" class="ref-h" value="${ref.height_px || ""}" placeholder="opt H" min="256" max="5760" style="padding: 0.25rem 0.45rem; font-size: 0.8rem; width: 100%;">
        </div>
      </div>
      <div class="ref-dim-notice" style="font-size: 0.72rem; color: var(--nord13); display: none;"></div>
    `;

    const captionInput = card.querySelector(".ref-caption");
    const sourceInput = card.querySelector(".ref-source");
    const wInput = card.querySelector(".ref-w");
    const hInput = card.querySelector(".ref-h");
    const dimNotice = card.querySelector(".ref-dim-notice");

    const checkDims = () => {
      const w = parseInt(wInput.value, 10);
      const h = parseInt(hInput.value, 10);
      if (w && h) {
        const ratio = w / h;
        if (w < 256 || w > 5760 || h < 256 || h > 5760) {
          dimNotice.textContent = "Advisory: Dimensions outside 256–5760 px will emit a warning (PF-20).";
          dimNotice.style.display = "block";
        } else if (ratio < 0.4 || ratio > 2.5) {
          dimNotice.textContent = `Advisory: Aspect ratio ${ratio.toFixed(2)} outside [0.4, 2.5] will emit a warning (PF-20).`;
          dimNotice.style.display = "block";
        } else {
          dimNotice.style.display = "none";
        }
      } else {
        dimNotice.style.display = "none";
      }
    };
    checkDims();

    const saveRef = async () => {
      const payload = {
        caption: captionInput.value,
        source_file: sourceInput.value,
        width_px: wInput.value ? parseInt(wInput.value, 10) : null,
        height_px: hInput.value ? parseInt(hInput.value, 10) : null,
      };
      await fetch(`/api/clips/${clipId}/references/${ref.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      checkDims();
      if (onUpdate) onUpdate({});
    };

    captionInput.addEventListener("change", saveRef);
    sourceInput.addEventListener("change", saveRef);
    wInput.addEventListener("change", saveRef);
    hInput.addEventListener("change", saveRef);

    container.appendChild(card);
  });
}

async function updateInstructionPreview(clipId, mode, shotCount, durationS, previewBox) {
  try {
    const res = await fetch(`/api/clips/${clipId}/instruction-preview`);
    if (res.ok) {
      const data = await res.json();
      previewBox.textContent = data.instruction_line || "(no instruction line generated)";
    }
  } catch (err) {
    console.error("Failed to load instruction preview", err);
  }
}
