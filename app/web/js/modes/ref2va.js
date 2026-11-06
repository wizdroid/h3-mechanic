/**
 * REF2VA Mode View Component (§4.4.6, §7.4, §8.3–§8.6, Appendix A.9)
 *
 * Full-Reference Flat Single-Canvas Interface (Criterion A-24):
 * Displays all four cards simultaneously without wizard-stepper gating:
 * - Card 1: Reference Tokens Card (<Picture N>, <Audio N>, <Video N>, live budget counters)
 * - Card 2: Subjects & Picture Mapping Card (0/1/multiple pictures per S-03, deterministic preview)
 * - Card 3: Shot Editor & Dialogue Card (shots, camera moves, landings, dialogue lines, audio timbre)
 * - Card 4: Action Bar & Retention Analysis Card (task types, retention table, sync)
 */

export async function renderREF2VAForm(container, clip, onUpdate) {
  container.innerHTML = "";

  const formWrapper = document.createElement("div");
  formWrapper.style.display = "flex";
  formWrapper.style.flexDirection = "column";
  formWrapper.style.gap = "1.2rem";

  // Banner
  const banner = document.createElement("div");
  banner.style.padding = "0.6rem 0.9rem";
  banner.style.background = "var(--bg-elevated)";
  banner.style.borderLeft = "3px solid var(--accent)";
  banner.style.borderRadius = "4px";
  banner.style.fontSize = "0.82rem";
  banner.style.color = "var(--text-secondary)";
  banner.innerHTML = `<strong>REF2VA Mode</strong>: Flat single-canvas reference-to-video prompt workspace. All cards are visible simultaneously for rapid iteration.`;
  formWrapper.appendChild(banner);

  const clipId = clip.id;

  // Container references for the 4 cards
  const card1 = document.createElement("div");
  card1.className = "ref2va-card panel";
  card1.style.border = "1px solid var(--border-color)";
  card1.style.borderRadius = "6px";
  card1.style.padding = "0.9rem";
  card1.style.background = "var(--bg-surface)";

  const card2 = document.createElement("div");
  card2.className = "ref2va-card panel";
  card2.style.border = "1px solid var(--border-color)";
  card2.style.borderRadius = "6px";
  card2.style.padding = "0.9rem";
  card2.style.background = "var(--bg-surface)";

  const card3 = document.createElement("div");
  card3.className = "ref2va-card panel";
  card3.style.border = "1px solid var(--border-color)";
  card3.style.borderRadius = "6px";
  card3.style.padding = "0.9rem";
  card3.style.background = "var(--bg-surface)";

  const card4 = document.createElement("div");
  card4.className = "ref2va-card panel";
  card4.style.border = "1px solid var(--border-color)";
  card4.style.borderRadius = "6px";
  card4.style.padding = "0.9rem";
  card4.style.background = "var(--bg-surface)";

  formWrapper.appendChild(card1);
  formWrapper.appendChild(card2);
  formWrapper.appendChild(card3);
  formWrapper.appendChild(card4);
  container.appendChild(formWrapper);

  // Initial load of all 4 cards
  await renderCard1ReferenceTokens(card1, clipId, () => {
    // When references change, refresh card 2, 3, 4
    renderCard2Subjects(card2, clipId, () => renderCard4Retention(card4, clipId));
    renderCard3ShotsAndDialogue(card3, clipId, clip, onUpdate);
    renderCard4Retention(card4, clipId);
  });

  await renderCard2Subjects(card2, clipId, () => {
    // When subjects change, refresh card 4 retention
    renderCard4Retention(card4, clipId);
  });

  await renderCard3ShotsAndDialogue(card3, clipId, clip, onUpdate);
  await renderCard4Retention(card4, clipId);
}


// ==============================================================================
// CARD 1: REFERENCE TOKENS CARD (§4.4.6, §6.1, §6.4, PF-20, Criterion A-11)
// ==============================================================================

async function renderCard1ReferenceTokens(cardElem, clipId, onRefsChanged) {
  let refs = [];
  try {
    const res = await fetch(`/api/clips/${clipId}/references`);
    if (res.ok) refs = await res.json();
  } catch (err) {
    console.error("Failed to fetch references:", err);
  }

  const imgCount = refs.filter((r) => r.kind === "image").length;
  const vidCount = refs.filter((r) => r.kind === "video").length;
  const audCount = refs.filter((r) => r.kind === "audio").length;
  const totalCount = refs.length;

  cardElem.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.4rem;">
      <div>
        <strong style="color: var(--accent); font-size: 0.95rem;">Card 1: Reference Tokens</strong>
        <div style="font-size: 0.76rem; color: var(--text-muted);">&lt;Picture N&gt;, &lt;Audio N&gt;, &lt;Video N&gt; metadata tokens</div>
      </div>
      <!-- Live Budget Counters (§6.1, PF-20) -->
      <div style="display: flex; gap: 0.4rem; font-size: 0.75rem; font-family: monospace;">
        <span class="badge" style="background: ${imgCount > 9 ? "var(--nord11)" : "var(--bg-elevated)"}; border: 1px solid var(--border-color);">
          Images: <strong>${imgCount}</strong>/9
        </span>
        <span class="badge" style="background: ${vidCount > 3 ? "var(--nord11)" : "var(--bg-elevated)"}; border: 1px solid var(--border-color);">
          Videos: <strong>${vidCount}</strong>/3
        </span>
        <span class="badge" style="background: ${audCount > 3 ? "var(--nord11)" : "var(--bg-elevated)"}; border: 1px solid var(--border-color);">
          Audio: <strong>${audCount}</strong>/3
        </span>
        <span class="badge" style="background: ${totalCount > 12 ? "var(--nord11)" : "var(--bg-elevated)"}; border: 1px solid var(--border-color);">
          Total: <strong>${totalCount}</strong>/12
        </span>
      </div>
    </div>

    <!-- Tokens List -->
    <div id="ref-tokens-list" style="display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 0.8rem; max-height: 250px; overflow-y: auto;">
      ${refs.length === 0 ? `<div style="color: var(--text-muted); font-size: 0.8rem; padding: 0.4rem;">No reference tokens added yet. Add an image, video, or audio reference below.</div>` : ""}
    </div>

    <!-- Add Reference Token Bar -->
    <div style="background: var(--bg-elevated); padding: 0.6rem; border-radius: 5px; border: 1px solid var(--border-color);">
      <div style="font-size: 0.8rem; font-weight: bold; margin-bottom: 0.4rem; color: var(--text-primary);">+ Add Reference Token</div>
      <div style="display: grid; grid-template-columns: 90px 1fr 1fr auto; gap: 0.4rem; align-items: center;">
        <select id="new-ref-kind" style="padding: 0.3rem; font-size: 0.8rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
          <option value="image">Image</option>
          <option value="video">Video</option>
          <option value="audio">Audio</option>
        </select>
        <input type="text" id="new-ref-file" placeholder="plate_01.png" style="padding: 0.3rem; font-size: 0.8rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
        <input type="text" id="new-ref-caption" placeholder="Caption / description" style="padding: 0.3rem; font-size: 0.8rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
        <button id="btn-add-ref-token" class="btn btn-primary" style="font-size: 0.8rem; padding: 0.3rem 0.7rem;">Add Token</button>
      </div>
      <div style="display: flex; gap: 0.6rem; margin-top: 0.4rem; font-size: 0.75rem; color: var(--text-secondary);">
        <label>Width: <input type="number" id="new-ref-w" placeholder="1024" style="width: 60px; font-size: 0.75rem;"></label>
        <label>Height: <input type="number" id="new-ref-h" placeholder="768" style="width: 60px; font-size: 0.75rem;"></label>
        <label>Duration (ms): <input type="number" id="new-ref-dur" placeholder="5000" style="width: 70px; font-size: 0.75rem;"></label>
      </div>
    </div>
  `;

  const listContainer = cardElem.querySelector("#ref-tokens-list");
  refs.forEach((ref, idx) => {
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.alignItems = "center";
    row.style.gap = "0.5rem";
    row.style.padding = "0.35rem 0.5rem";
    row.style.background = "var(--bg-elevated)";
    row.style.borderRadius = "4px";
    row.style.fontSize = "0.82rem";

    const labelStr = ref.kind === "image" ? `&lt;Picture ${ref.ordinal}&gt;` : (ref.kind === "video" ? `&lt;Video ${ref.ordinal}&gt;` : `&lt;Audio ${ref.ordinal}&gt;`);
    const fileStr = ref.plate_filename || ref.source_file || "MISSING";
    const durStr = ref.duration_ms ? ` (${(ref.duration_ms / 1000).toFixed(1)}s)` : "";

    row.innerHTML = `
      <span style="font-family: monospace; font-weight: bold; color: var(--accent); min-width: 85px;">${labelStr}</span>
      <span class="badge" style="font-size: 0.72rem; text-transform: uppercase;">${ref.kind}</span>
      <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${fileStr}: ${ref.caption || ""}">${fileStr}${durStr} ${ref.caption ? `— ${ref.caption}` : ""}</span>
      <div style="display: flex; gap: 0.2rem;">
        <button class="btn btn-sm btn-move-up" ${idx === 0 ? "disabled" : ""} title="Move Up">↑</button>
        <button class="btn btn-sm btn-move-down" ${idx === refs.length - 1 ? "disabled" : ""} title="Move Down">↓</button>
        <button class="btn btn-sm btn-danger btn-del-ref" title="Delete">✕</button>
      </div>
    `;

    // Move Up
    row.querySelector(".btn-move-up")?.addEventListener("click", async () => {
      if (idx > 0) {
        const newOrder = [...refs];
        const temp = newOrder[idx - 1];
        newOrder[idx - 1] = newOrder[idx];
        newOrder[idx] = temp;
        await fetch(`/api/clips/${clipId}/references/reorder`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reference_ids: newOrder.map((r) => r.id) }),
        });
        renderCard1ReferenceTokens(cardElem, clipId, onRefsChanged);
        if (onRefsChanged) onRefsChanged();
      }
    });

    // Move Down
    row.querySelector(".btn-move-down")?.addEventListener("click", async () => {
      if (idx < refs.length - 1) {
        const newOrder = [...refs];
        const temp = newOrder[idx + 1];
        newOrder[idx + 1] = newOrder[idx];
        newOrder[idx] = temp;
        await fetch(`/api/clips/${clipId}/references/reorder`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reference_ids: newOrder.map((r) => r.id) }),
        });
        renderCard1ReferenceTokens(cardElem, clipId, onRefsChanged);
        if (onRefsChanged) onRefsChanged();
      }
    });

    // Delete
    row.querySelector(".btn-del-ref")?.addEventListener("click", async () => {
      if (confirm(`Delete reference ${labelStr}?`)) {
        await fetch(`/api/references/${ref.id}`, { method: "DELETE" });
        renderCard1ReferenceTokens(cardElem, clipId, onRefsChanged);
        if (onRefsChanged) onRefsChanged();
      }
    });

    listContainer.appendChild(row);
  });

  // Add Ref Token Submit
  cardElem.querySelector("#btn-add-ref-token").addEventListener("click", async () => {
    const kind = cardElem.querySelector("#new-ref-kind").value;
    const file = cardElem.querySelector("#new-ref-file").value.trim();
    const caption = cardElem.querySelector("#new-ref-caption").value.trim();
    const w = parseInt(cardElem.querySelector("#new-ref-w").value, 10) || null;
    const h = parseInt(cardElem.querySelector("#new-ref-h").value, 10) || null;
    const dur = parseInt(cardElem.querySelector("#new-ref-dur").value, 10) || (kind === "image" ? null : 5000);

    const payload = {
      kind,
      plate_filename: file || (kind === "image" ? "plate.png" : (kind === "video" ? "video.mp4" : "audio.wav")),
      caption: caption || undefined,
      width_px: w,
      height_px: h,
      duration_ms: dur,
    };

    try {
      const res = await fetch(`/api/clips/${clipId}/references`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        renderCard1ReferenceTokens(cardElem, clipId, onRefsChanged);
        if (onRefsChanged) onRefsChanged();
      } else {
        const err = await res.json();
        alert(`Error adding reference: ${err.detail || JSON.stringify(err)}`);
      }
    } catch (e) {
      console.error(e);
    }
  });
}


// ==============================================================================
// CARD 2: SUBJECTS & PICTURE MAPPING CARD (§4.4.6, S-03, §8.3, Appendix A.9)
// ==============================================================================

async function renderCard2Subjects(cardElem, clipId, onSubjectsChanged) {
  let subjects = [];
  let subjectPictures = [];
  let references = [];
  let previewText = "";

  try {
    const [subRes, spRes, refRes, prevRes] = await Promise.all([
      fetch(`/api/clips/${clipId}/subjects`),
      fetch(`/api/clips/${clipId}/subject-pictures`),
      fetch(`/api/clips/${clipId}/references`),
      fetch(`/api/clips/${clipId}/subject-defs-preview`),
    ]);
    if (subRes.ok) subjects = await subRes.json();
    if (spRes.ok) subjectPictures = await spRes.json();
    if (refRes.ok) references = await refRes.json();
    if (prevRes.ok) {
      const pData = await prevRes.json();
      previewText = pData.subject_definitions || "";
    }
  } catch (e) {
    console.error("Failed to load subject data", e);
  }

  const imageRefs = references.filter((r) => r.kind === "image");

  cardElem.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.4rem;">
      <div>
        <strong style="color: var(--accent); font-size: 0.95rem;">Card 2: Subjects & Picture Mapping</strong>
        <div style="font-size: 0.76rem; color: var(--text-muted);">S-03 Many-to-many linking (0 pictures, 1 picture, or multiple pictures per subject)</div>
      </div>
      <span class="badge" style="background: var(--bg-elevated); border: 1px solid var(--border-color);">
        Subjects: <strong>${subjects.length}</strong>
      </span>
    </div>

    <!-- Live Deterministic Subject Definitions Preview Box (§8.3) -->
    <div style="margin-bottom: 0.8rem; background: var(--bg-elevated); border: 1px solid var(--border-color); border-radius: 5px; padding: 0.5rem 0.7rem;">
      <div style="font-size: 0.76rem; font-weight: bold; color: var(--text-secondary); margin-bottom: 0.2rem; display: flex; justify-content: space-between;">
        <span>Deterministic Compiled Definitions Preview (§8.3):</span>
        <span style="color: var(--accent);">Zero LLM Calls</span>
      </div>
      <pre style="margin: 0; font-size: 0.76rem; color: var(--nord8); white-space: pre-wrap; font-family: monospace; max-height: 100px; overflow-y: auto;">${previewText || "(No subjects defined yet)"}</pre>
    </div>

    <!-- Subjects List -->
    <div id="subjects-list-container" style="display: flex; flex-direction: column; gap: 0.6rem; margin-bottom: 0.8rem; max-height: 320px; overflow-y: auto;">
      ${subjects.length === 0 ? `<div style="color: var(--text-muted); font-size: 0.8rem; padding: 0.4rem;">No subjects defined yet. Add your first subject below.</div>` : ""}
    </div>

    <!-- Add Subject Form -->
    <div style="background: var(--bg-elevated); padding: 0.6rem; border-radius: 5px; border: 1px solid var(--border-color);">
      <div style="font-size: 0.8rem; font-weight: bold; margin-bottom: 0.4rem; color: var(--text-primary);">+ Add Subject</div>
      <div style="display: grid; grid-template-columns: 110px 1fr 70px 100px auto; gap: 0.4rem; align-items: center;">
        <select id="new-sub-role" style="padding: 0.3rem; font-size: 0.8rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
          <option value="person">person</option>
          <option value="character">character</option>
          <option value="location">location</option>
          <option value="outfit">outfit</option>
          <option value="prop">prop</option>
          <option value="weapon">weapon</option>
          <option value="vehicle">vehicle</option>
        </select>
        <input type="text" id="new-sub-role-phrase" placeholder="officer" style="padding: 0.3rem; font-size: 0.8rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
        <select id="new-sub-pronoun" style="padding: 0.3rem; font-size: 0.8rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
          <option value="his">his</option>
          <option value="her">her</option>
          <option value="its">its</option>
        </select>
        <input type="text" id="new-sub-outfit-noun" placeholder="uniform" style="padding: 0.3rem; font-size: 0.8rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
        <button id="btn-add-subject" class="btn btn-primary" style="font-size: 0.8rem; padding: 0.3rem 0.7rem;">Add Subject</button>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; margin-top: 0.4rem;">
        <input type="text" id="new-sub-appositive" placeholder="optional appositive: a prison guard" style="padding: 0.25rem 0.4rem; font-size: 0.75rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
        <input type="text" id="new-sub-features" placeholder="feature list: walls, floor, cell doors, and layout" style="padding: 0.25rem 0.4rem; font-size: 0.75rem; border-radius: 4px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
      </div>
    </div>
  `;

  const listContainer = cardElem.querySelector("#subjects-list-container");

  subjects.forEach((subj) => {
    const sBox = document.createElement("div");
    sBox.style.background = "var(--bg-elevated)";
    sBox.style.border = "1px solid var(--border-color)";
    sBox.style.borderRadius = "5px";
    sBox.style.padding = "0.5rem 0.6rem";
    sBox.style.display = "flex";
    sBox.style.flexDirection = "column";
    sBox.style.gap = "0.4rem";

    const labelStr = `&lt;Subject ${subj.ordinal}&gt;`;
    const linkedLinks = subjectPictures.filter((sp) => sp.subject_id === subj.id);

    sBox.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <strong style="color: var(--accent); font-family: monospace;">${labelStr}</strong>
          <span class="badge">${subj.role}</span>
          <span style="font-size: 0.82rem; color: var(--text-primary); font-weight: 500;">the ${subj.role_phrase || "character"}</span>
          ${subj.appositive ? `<span style="font-size: 0.76rem; color: var(--text-muted);">(${subj.appositive})</span>` : ""}
        </div>
        <button class="btn btn-sm btn-danger btn-del-subj" title="Delete Subject">✕</button>
      </div>

      <!-- Linked Pictures Chips (Many-to-Many S-03) -->
      <div style="display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center; margin-top: 0.2rem;">
        <span style="font-size: 0.74rem; color: var(--text-secondary);">Linked Pictures:</span>
        ${linkedLinks.length === 0 ? `<span style="font-size: 0.74rem; color: var(--nord14); font-style: italic;">[0 Pictures: Text-Only Formula]</span>` : ""}
        <div class="picture-chips-container" style="display: flex; flex-wrap: wrap; gap: 0.3rem;"></div>
        
        <!-- Add Link Selector -->
        <div style="display: inline-flex; align-items: center; gap: 0.2rem; margin-left: auto;">
          <select class="sel-link-pic" style="font-size: 0.72rem; padding: 0.15rem 0.3rem; border-radius: 3px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
            ${imageRefs.map((r) => `<option value="${r.id}">&lt;Picture ${r.ordinal}&gt;</option>`).join("")}
          </select>
          <select class="sel-link-role" style="font-size: 0.72rem; padding: 0.15rem 0.3rem; border-radius: 3px; background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border-color);">
            <option value="identity_anchor">identity_anchor (face/build)</option>
            <option value="outfit">outfit</option>
            <option value="prop">prop</option>
            <option value="location">location</option>
            <option value="first_frame">first_frame (anchor)</option>
            <option value="keyframe">keyframe (anchor)</option>
            <option value="last_frame">last_frame (anchor)</option>
            <option value="composition_anchor">composition_anchor</option>
          </select>
          <button class="btn btn-sm btn-add-link" style="font-size: 0.72rem; padding: 0.15rem 0.4rem;">+ Link</button>
        </div>
      </div>
    `;

    // Render linked chips
    const chipsBox = sBox.querySelector(".picture-chips-container");
    linkedLinks.forEach((link) => {
      const ref = references.find((r) => r.id === link.reference_id);
      const picLabel = ref ? `&lt;Picture ${ref.ordinal}&gt;` : `Ref #${link.reference_id}`;
      const chip = document.createElement("span");
      chip.className = "badge";
      chip.style.background = "var(--bg-surface)";
      chip.style.border = "1px solid var(--border-color)";
      chip.style.fontSize = "0.72rem";
      chip.style.display = "inline-flex";
      chip.style.alignItems = "center";
      chip.style.gap = "0.3rem";
      chip.innerHTML = `
        <strong>${picLabel}</strong> (${link.reference_role})
        <span class="btn-del-link" style="cursor: pointer; color: var(--nord11); font-weight: bold;">×</span>
      `;
      chip.querySelector(".btn-del-link").addEventListener("click", async () => {
        await fetch(`/api/subject-pictures/${link.id}`, { method: "DELETE" });
        renderCard2Subjects(cardElem, clipId, onSubjectsChanged);
        if (onSubjectsChanged) onSubjectsChanged();
      });
      chipsBox.appendChild(chip);
    });

    // Add Link Button
    sBox.querySelector(".btn-add-link")?.addEventListener("click", async () => {
      const picId = parseInt(sBox.querySelector(".sel-link-pic").value, 10);
      const linkRole = sBox.querySelector(".sel-link-role").value;
      if (!picId) return;
      await fetch(`/api/clips/${clipId}/subject-pictures`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          subject_id: subj.id,
          reference_id: picId,
          reference_role: linkRole,
          anchor_shot_ordinal: 1,
        }),
      });
      renderCard2Subjects(cardElem, clipId, onSubjectsChanged);
      if (onSubjectsChanged) onSubjectsChanged();
    });

    // Delete Subject Button
    sBox.querySelector(".btn-del-subj").addEventListener("click", async () => {
      if (confirm(`Delete subject ${labelStr}?`)) {
        await fetch(`/api/subjects/${subj.id}`, { method: "DELETE" });
        renderCard2Subjects(cardElem, clipId, onSubjectsChanged);
        if (onSubjectsChanged) onSubjectsChanged();
      }
    });

    listContainer.appendChild(sBox);
  });

  // Add Subject Submit
  cardElem.querySelector("#btn-add-subject").addEventListener("click", async () => {
    const role = cardElem.querySelector("#new-sub-role").value;
    const rolePhrase = cardElem.querySelector("#new-sub-role-phrase").value.trim();
    const pronoun = cardElem.querySelector("#new-sub-pronoun").value;
    const outfitNoun = cardElem.querySelector("#new-sub-outfit-noun").value.trim();
    const appositive = cardElem.querySelector("#new-sub-appositive").value.trim();
    const features = cardElem.querySelector("#new-sub-features").value.trim();

    if (!rolePhrase) {
      alert("Please enter a role phrase (e.g. officer, informant, cell corridor)");
      return;
    }

    try {
      const res = await fetch(`/api/clips/${clipId}/subjects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role,
          role_phrase: rolePhrase,
          pronoun,
          outfit_noun: outfitNoun || "outfit",
          appositive,
          feature_list: features,
        }),
      });
      if (res.ok) {
        renderCard2Subjects(cardElem, clipId, onSubjectsChanged);
        if (onSubjectsChanged) onSubjectsChanged();
      }
    } catch (e) {
      console.error(e);
    }
  });
}


// ==============================================================================
// CARD 3: SHOT EDITOR & DIALOGUE CARD (§4.4.6, §8.0, §9.5, §9.6)
// ==============================================================================

async function renderCard3ShotsAndDialogue(cardElem, clipId, clip, onUpdate) {
  let shots = [];
  let references = [];
  try {
    const [shotRes, refRes] = await Promise.all([
      fetch(`/api/clips/${clipId}/shots`),
      fetch(`/api/clips/${clipId}/references`),
    ]);
    if (shotRes.ok) shots = await shotRes.json();
    if (refRes.ok) references = await refRes.json();
  } catch (e) {
    console.error("Failed to load shots", e);
  }

  cardElem.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.4rem;">
      <div>
        <strong style="color: var(--accent); font-size: 0.95rem;">Card 3: Shot Editor & Dialogue</strong>
        <div style="font-size: 0.76rem; color: var(--text-muted);">Exact camera moves, landings, timestamps, dialogue lines, and audio timbre links</div>
      </div>
      <button id="btn-add-shot" class="btn btn-sm btn-primary">+ Add Shot</button>
    </div>

    <!-- Shots Table -->
    <div style="max-height: 200px; overflow-y: auto; margin-bottom: 0.8rem; border: 1px solid var(--border-color); border-radius: 5px;">
      <table class="dialogue-table" style="width: 100%; font-size: 0.78rem;">
        <thead>
          <tr>
            <th style="width: 60px;">Shot</th>
            <th style="width: 80px;">Start Time</th>
            <th style="width: 110px;">Size</th>
            <th style="width: 110px;">Angle</th>
            <th>Camera Move & Landing</th>
            <th style="width: 70px;">Pacing</th>
            <th style="width: 35px;"></th>
          </tr>
        </thead>
        <tbody id="shots-tbody">
          ${shots.length === 0 ? `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No planned shots. Click '+ Add Shot' to create one.</td></tr>` : ""}
        </tbody>
      </table>
    </div>

    <!-- Dialogue Lines Container with Audio Timbre Links -->
    <div id="dialogue-lines-wrapper"></div>
  `;

  // Render Shots Rows
  const tbody = cardElem.querySelector("#shots-tbody");
  shots.forEach((s) => {
    const tr = document.createElement("tr");
    const isShot1 = s.ordinal === 1;
    const startStr = isShot1 ? "00:00.000" : formatMs(s.start_ms || 0);

    tr.innerHTML = `
      <td style="font-weight: bold; font-family: monospace; color: var(--accent); text-align: center;">[Shot ${s.ordinal}]</td>
      <td>
        <input type="text" class="shot-start" value="${startStr}" ${isShot1 ? "disabled title='Shot 1 is locked to 00:00.000'" : ""} style="width: 100%; font-family: monospace; padding: 0.15rem 0.3rem;">
      </td>
      <td>
        <select class="shot-size" style="width: 100%; padding: 0.15rem;">
          <option value="a close-up" ${s.size === "a close-up" ? "selected" : ""}>close-up</option>
          <option value="a medium close-up" ${s.size === "a medium close-up" ? "selected" : ""}>medium close-up</option>
          <option value="a medium shot" ${s.size === "a medium shot" ? "selected" : ""}>medium shot</option>
          <option value="a wide shot" ${s.size === "a wide shot" ? "selected" : ""}>wide shot</option>
        </select>
      </td>
      <td>
        <select class="shot-angle" style="width: 100%; padding: 0.15rem;">
          <option value="at eye level" ${s.angle === "at eye level" ? "selected" : ""}>at eye level</option>
          <option value="from a low angle" ${s.angle === "from a low angle" ? "selected" : ""}>low angle</option>
          <option value="from a high angle" ${s.angle === "from a high angle" ? "selected" : ""}>high angle</option>
        </select>
      </td>
      <td>
        <input type="text" class="shot-cam" value="${s.camera_phrase || "The camera pushes in toward the subject"}" style="width: 100%; padding: 0.15rem 0.3rem;" placeholder="Camera move with landing: ... toward / revealing / onto / as ...">
      </td>
      <td>
        <select class="shot-pacing" style="width: 100%; padding: 0.15rem;">
          <option value="silent" ${s.pacing === "silent" ? "selected" : ""}>silent</option>
          <option value="action" ${s.pacing === "action" ? "selected" : ""}>action</option>
        </select>
      </td>
      <td style="text-align: center;">
        <button class="btn btn-sm btn-danger btn-del-shot" title="Delete Shot">✕</button>
      </td>
    `;

    // Save shot edits on blur
    const saveShot = async () => {
      const sizeVal = tr.querySelector(".shot-size").value;
      const angleVal = tr.querySelector(".shot-angle").value;
      const camVal = tr.querySelector(".shot-cam").value.trim();
      const pacingVal = tr.querySelector(".shot-pacing").value;
      let startMs = s.start_ms;
      if (!isShot1) {
        startMs = parseMs(tr.querySelector(".shot-start").value);
      }
      await fetch(`/api/shots/${s.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          size: sizeVal,
          angle: angleVal,
          camera_phrase: camVal,
          pacing: pacingVal,
          start_ms: startMs,
        }),
      });
    };

    tr.querySelector(".shot-size").addEventListener("change", saveShot);
    tr.querySelector(".shot-angle").addEventListener("change", saveShot);
    tr.querySelector(".shot-cam").addEventListener("blur", saveShot);
    tr.querySelector(".shot-pacing").addEventListener("change", saveShot);
    if (!isShot1) {
      tr.querySelector(".shot-start").addEventListener("blur", saveShot);
    }

    // Delete Shot
    tr.querySelector(".btn-del-shot").addEventListener("click", async () => {
      if (confirm(`Delete [Shot ${s.ordinal}]?`)) {
        await fetch(`/api/shots/${s.id}`, { method: "DELETE" });
        renderCard3ShotsAndDialogue(cardElem, clipId, clip, onUpdate);
      }
    });

    tbody.appendChild(tr);
  });

  // Add Shot Button
  cardElem.querySelector("#btn-add-shot").addEventListener("click", async () => {
    const nextOrd = shots.length + 1;
    const startMs = shots.length > 0 ? (shots.length * 3000) : 0;
    await fetch(`/api/clips/${clipId}/shots`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_ms: startMs,
        size: "a medium close-up",
        angle: "at eye level",
        camera_phrase: "The camera pushes in toward the subject",
        pacing: "action",
      }),
    });
    renderCard3ShotsAndDialogue(cardElem, clipId, clip, onUpdate);
  });

  // Render Dialogue Lines Sub-section using app shared dialogue components
  const dlgWrapper = cardElem.querySelector("#dialogue-lines-wrapper");
  import("./t2va.js").then((mod) => {
    mod.renderDialogueLinesSection(dlgWrapper, clip, onUpdate);
  });
}


// ==============================================================================
// CARD 4: ACTION BAR & RETENTION ANALYSIS CARD (§4.4.6, §6.4, §8.5, §8.6, PF-22)
// ==============================================================================

async function renderCard4Retention(cardElem, clipId) {
  let retentionRows = [];
  let clipData = {};
  try {
    const [retRes, clipRes] = await Promise.all([
      fetch(`/api/clips/${clipId}/retention`),
      fetch(`/api/clips/${clipId}`),
    ]);
    if (retRes.ok) retentionRows = await retRes.json();
    if (clipRes.ok) clipData = await clipRes.json();
  } catch (e) {
    console.error("Failed to load retention data", e);
  }

  // Parse task types
  let activeTypes = ["reference generation"];
  try {
    const raw = clipData.task_types_json;
    if (raw) activeTypes = typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch (e) {}

  const allTaskTypes = [
    { id: "reference generation", label: "reference generation (guidance)" },
    { id: "keyframe completion", label: "keyframe completion (frame anchor)" },
    { id: "video editing", label: "video editing (opens 'The target video is an edited version of...')" },
    { id: "video continuation", label: "video continuation" },
    { id: "audio reuse", label: "audio reuse" },
    { id: "audio reference", label: "audio reference (timbre)" },
  ];

  cardElem.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.4rem;">
      <div>
        <strong style="color: var(--accent); font-size: 0.95rem;">Card 4: Action Bar & Retention Analysis</strong>
        <div style="font-size: 0.76rem; color: var(--text-muted);">Task types, reference preservation markers, and justification reasons</div>
      </div>
      <button id="btn-sync-retention" class="btn btn-sm" title="Synchronize retention rows with current subjects and references">Sync Rows</button>
    </div>

    <!-- Task Types Checklist (§8.5, Appendix A.9) -->
    <div style="background: var(--bg-elevated); padding: 0.6rem; border-radius: 5px; border: 1px solid var(--border-color); margin-bottom: 0.8rem;">
      <div style="font-size: 0.8rem; font-weight: bold; margin-bottom: 0.4rem; color: var(--text-primary);">
        Task Types Prefix (§8.5): <span style="font-family: monospace; color: var(--accent);">[${activeTypes.join(" + ")}]</span>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; font-size: 0.78rem;">
        ${allTaskTypes.map((t) => `
          <label style="display: flex; align-items: center; gap: 0.4rem; cursor: pointer;">
            <input type="checkbox" class="cb-task-type" value="${t.id}" ${activeTypes.includes(t.id) ? "checked" : ""}>
            <span>${t.label}</span>
          </label>
        `).join("")}
      </div>
    </div>

    <!-- Retention Analysis Table (§8.6, PF-22) -->
    <div style="max-height: 240px; overflow-y: auto; border: 1px solid var(--border-color); border-radius: 5px;">
      <table class="dialogue-table" style="width: 100%; font-size: 0.78rem;">
        <thead>
          <tr>
            <th style="width: 120px;">Item</th>
            <th style="width: 140px;">Parenthetical</th>
            <th style="width: 140px;">Retention Marker</th>
            <th>Reason (≤ 25 words, no Sx)</th>
          </tr>
        </thead>
        <tbody id="retention-tbody">
          ${retentionRows.length === 0 ? `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 0.8rem;">No retention entries. Click 'Sync Rows' to populate from subjects and references.</td></tr>` : ""}
        </tbody>
      </table>
    </div>
  `;

  // Handle Task Types Checkbox Toggles
  const checkboxes = cardElem.querySelectorAll(".cb-task-type");
  checkboxes.forEach((cb) => {
    cb.addEventListener("change", async () => {
      const selected = Array.from(checkboxes)
        .filter((c) => c.checked)
        .map((c) => c.value);
      await fetch(`/api/clips/${clipId}/task-types`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_types: selected }),
      });
      renderCard4Retention(cardElem, clipId);
    });
  });

  // Handle Sync Button
  cardElem.querySelector("#btn-sync-retention").addEventListener("click", async () => {
    await fetch(`/api/clips/${clipId}/retention/sync`, { method: "POST" });
    renderCard4Retention(cardElem, clipId);
  });

  // Render Retention Rows
  const tbody = cardElem.querySelector("#retention-tbody");
  retentionRows.forEach((row) => {
    const tr = document.createElement("tr");
    const isVisual = row.area === "visual";
    const markerOptions = isVisual
      ? ["fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference"]
      : ["fully_copy", "partially_copy", "reference", "weak_reference"];

    const itemLabel = row.subject_id ? `&lt;Subject #${row.subject_id}&gt;` : `&lt;Ref #${row.reference_id}&gt;`;

    tr.innerHTML = `
      <td style="font-weight: bold; font-family: monospace; color: var(--accent);">${itemLabel}</td>
      <td>
        <input type="text" class="ret-paren" value="${row.parenthetical || ""}" style="width: 100%; padding: 0.15rem 0.3rem; font-size: 0.76rem;" placeholder="(appears in [Shot 1])">
      </td>
      <td>
        <select class="ret-marker" style="width: 100%; padding: 0.15rem; font-size: 0.76rem;">
          ${markerOptions.map((m) => `<option value="${m}" ${row.marker === m ? "selected" : ""}>${m}</option>`).join("")}
        </select>
      </td>
      <td>
        <input type="text" class="ret-reason" value="${row.reason || ""}" style="width: 100%; padding: 0.15rem 0.3rem; font-size: 0.76rem;" placeholder="Reason (max 25 words, no Sx tags)">
      </td>
    `;

    // Save on blur
    const saveRow = async () => {
      const markerVal = tr.querySelector(".ret-marker").value;
      const reasonVal = tr.querySelector(".ret-reason").value.trim();
      const parenVal = tr.querySelector(".ret-paren").value.trim();
      await fetch(`/api/retention/${row.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          marker: markerVal,
          reason: reasonVal,
          parenthetical: parenVal,
        }),
      });
    };

    tr.querySelector(".ret-marker").addEventListener("change", saveRow);
    tr.querySelector(".ret-reason").addEventListener("blur", saveRow);
    tr.querySelector(".ret-paren").addEventListener("blur", saveRow);

    tbody.appendChild(tr);
  });
}


// ==============================================================================
// HELPERS
// ==============================================================================

function formatMs(ms) {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  const mmm = ms % 1000;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(mmm).padStart(3, "0")}`;
}

function parseMs(str) {
  const m = str.match(/(\d{2}):(\d{2})\.(\d{3})/);
  if (!m) return 0;
  return parseInt(m[1], 10) * 60000 + parseInt(m[2], 10) * 1000 + parseInt(m[3], 10);
}
