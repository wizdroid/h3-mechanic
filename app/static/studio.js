/* Extra editor surfaces. Loaded after app.js, before the first paint finishes. */

S.view = "editor";
S.undoStack = [];
S.redoStack = [];
S.sceneId = "sc-default";
S.query = "";
S.token = localStorage.getItem("h3m:token") || (Math.random().toString(16).slice(2) + Math.random().toString(16).slice(2));
localStorage.setItem("h3m:token", S.token);

function pushUndo() {
  S.undoStack.push(JSON.stringify(S.project));
  if (S.undoStack.length > 60) S.undoStack.shift();
  S.redoStack = [];
}
function restore(json) {
  S.project = JSON.parse(json);
  ensureClip();
  paint();
  scheduleAssemble();
  saveLocal();
}

const _visibleClips = visibleClips;
visibleClips = function () {
  let list = _visibleClips();
  if (S.sceneId) list = list.filter((c) => (c.sceneId || "sc-default") === S.sceneId);
  if (S.query) {
    const q = S.query.toLowerCase();
    list = list.filter((c) => JSON.stringify(c).toLowerCase().includes(q));
  }
  if (S.onlyErrors) list = list.filter((c) => S._marks && S._marks[c.id]);
  return list;
};

const _blankClip = blankClip;
blankClip = function (mode) {
  const clip = _blankClip(mode);
  clip.sceneId = S.sceneId || "sc-default";
  clip.status = "draft";
  clip.clipKind = "narrative";
  clip.autoTasks = true;
  const scene = (S.project.scenes || []).find((s) => s.id === clip.sceneId);
  if (scene) scene.clipIds.push(clip.id);
  return clip;
};

const _paintHeader = paintHeader;
paintHeader = function () {
  _paintHeader();
  const bar = document.getElementById("header-actions");
  if (!bar) return;
  bar.insertAdjacentHTML("afterbegin", `
    <button type="button" id="act-undo" title="Undo">Undo</button>
    <button type="button" id="act-redo" title="Redo">Redo</button>
    <button type="button" id="act-episode">Episode</button>
    <button type="button" id="act-library">Library</button>
    <button type="button" id="act-dashboard">Checks</button>
    <button type="button" id="act-sheets">Sheets</button>
    <button type="button" id="act-palette">Commands</button>
  `);
  const title = document.querySelector("header h1");
  if (title) title.classList.toggle("dirty", !!S.dirty);
};

const _paintEditorShell = paintEditorShell;
paintEditorShell = function () {
  if (S.view && S.view !== "editor") {
    document.getElementById("app").innerHTML = altView();
    return;
  }
  _paintEditorShell();
};

const _paintPreview = paintPreview;
paintPreview = function () {
  _paintPreview();
  const list = document.getElementById("validation-list");
  if (list) {
    list.querySelectorAll("li").forEach((li, i) => {
      const finding = (S.findings || [])[i];
      if (finding && finding.fix && !li.querySelector("[data-fix]")) {
        li.insertAdjacentHTML("beforeend", ` <button type="button" data-fix="${esc(finding.fix)}">Fix</button>`);
      }
    });
  }
  const meta = document.getElementById("prompt-meta");
  if (meta && S.words) meta.textContent += ` · ${S.words} words`;
  const bar = document.querySelector("#preview .bar");
  if (bar && !document.getElementById("act-payload")) {
    bar.insertAdjacentHTML("beforeend", `<button type="button" id="act-payload">API payload</button><button type="button" id="act-review-draft">Review AI draft</button>`);
  }
  if (S.review && S.review.length) {
    const host = document.getElementById("preview");
    if (host && !document.getElementById("draft-review")) {
      host.insertAdjacentHTML("beforeend", `<div id="draft-review"><h2>Draft sections</h2>
        ${S.review.map((row) => `<label class="check"><input type="checkbox" data-accept="${esc(row.id)}" ${row.locked ? "disabled" : "checked"} /> ${esc(row.title)}${row.locked ? " (locked)" : ""}<span class="hint">${esc(row.preview)}</span></label>`).join("")}
        <div class="bar"><button type="button" id="apply-sections">Apply selected</button><button type="button" id="drop-review">Close</button></div>
      </div>`);
    }
  }
};

window.h3Slot = function (name, a, b, c) {
  if (name === "rail") return railSlot();
  if (name === "after-meta") return metaSlot(a);
  if (name === "subject") return subjectSlot(a, b, c);
  if (name === "shot") return shotSlot(a, b, c);
  if (name === "before-sound") return soundSlot(a);
  return "";
};

function railSlot() {
  const scenes = (S.project && S.project.scenes) || [];
  const sceneOpts = scenes.map((s) => `<option value="${esc(s.id)}" ${s.id === S.sceneId ? "selected" : ""}>${esc(s.title)}</option>`).join("");
  const templates = (S.banks.templates || []).map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
  return `<div class="stack">
    <label>Scene <select id="scene-pick">${sceneOpts}</select></label>
    <div class="bar"><button type="button" id="add-scene">Add scene</button><button type="button" id="rename-scene">Rename</button></div>
    <label>Find <input id="clip-find" value="${esc(S.query || "")}" placeholder="name, line, path" /></label>
    <label class="check"><input type="checkbox" id="only-errors" ${S.onlyErrors ? "checked" : ""} /> Only clips with errors</label>
    <label>Template <span class="bar"><select id="template-name">${templates}</select><button type="button" id="apply-template">Apply</button></span></label>
    <div class="bar">
      <button type="button" id="dup-clip">Duplicate</button>
      <button type="button" id="var-clip">Variant</button>
      <button type="button" id="split-clip">Split</button>
      <button type="button" id="merge-clip">Merge next</button>
    </div>
  </div>`;
}

function metaSlot(clip) {
  const statuses = S.banks.statuses || [];
  const kinds = S.banks.clipKinds || [];
  return `<section class="card" id="sec-continuity">
    <h2>Clip standing</h2>
    <div class="grid">
      ${field("Status", `<select data-bind="status">${opt(statuses, clip.status || "draft")}</select>`)}
      ${field("Kind", `<select data-bind="clipKind">${opt(kinds, clip.clipKind || "narrative")}</select>`)}
      ${field("Screen direction", `<select data-bind="screenDirection">${opt(["", "ltr", "rtl"], clip.screenDirection || "", (v) => ({ "": "inherit", ltr: "frame-left to right", rtl: "frame-right to left" }[v] || v))}</select>`)}
    </div>
    <label class="check"><input type="checkbox" data-bind="autoTasks" ${clip.autoTasks !== false ? "checked" : ""} /> Add task types from anchors, video, and audio</label>
    <label class="check"><input type="checkbox" data-bind="lightLock" ${clip.lightLock ? "checked" : ""} /> Light comes only from the end-frame anchor</label>
    <label class="check"><input type="checkbox" data-bind="allowCuts" ${clip.allowCuts ? "checked" : ""} /> FL2VA may cut</label>
    <label>End state <textarea data-bind="endState" placeholder="Who is where, which way they face, the light, the wall.">${esc(clip.endState || "")}</textarea></label>
    <label>Facts the next clip must keep <textarea data-bind="facts" placeholder="khaki uniform&#10;north wall">${esc(clip.facts || "")}</textarea></label>
    <label>Carried in from the previous clip <textarea data-bind="carried" readonly>${esc(clip.carried || "")}</textarea></label>
    <label>What the still already looks like <input data-bind="frameNote" value="${esc(clip.frameNote || "")}" placeholder="night, sodium light" /></label>
    <label>Plate comment <textarea data-bind="platesComment" placeholder="# Eyeline and wall notes">${esc(clip.platesComment || "")}</textarea></label>
    <label>End still ${pathInput("endStill", clip.endStill || "")}</label>
    <label>Rendered file ${pathInput("renderPath", clip.renderPath || "")}</label>
    <label class="check"><input type="checkbox" data-bind="lockStyle" ${clip.lockStyle ? "checked" : ""} /> Lock the style opening against a draft</label>
    <p class="hint">${clip.variantOf ? "This clip is a variant of " + clip.variantOf : "Variants share the idea and export separately."}</p>
    ${clip.fileReport ? `<pre class="sheet">${esc(clip.fileReport)}</pre>` : ""}
    <div class="bar"><button type="button" id="continue-next">Continue into the next clip</button><button type="button" id="link-neighbors">Link neighboring clips</button><button type="button" id="probe-files">Measure files</button><button type="button" id="remove-clip">Remove clip</button></div>
  </section>`;
}

function subjectSlot(clip, subject, index) {
  const accents = [""].concat(S.banks.accents || []);
  const src = subject.imageFile ? `/api/thumb?path=${encodeURIComponent(subject.imageFile)}` : "";
  return `<div class="grid">
    ${src ? `<img class="thumb" alt="" src="${esc(src)}" />` : ""}
    <label class="check"><input type="checkbox" data-bind="subjects.${index}.identityLock" ${subject.identityLock ? "checked" : ""} /> Identity lock</label>
    <label class="check"><input type="checkbox" data-bind="subjects.${index}.identityOnly" ${subject.identityOnly ? "checked" : ""} /> Picture supplies identity only</label>
    <label class="check"><input type="checkbox" data-bind="subjects.${index}.turnaround" ${subject.turnaround ? "checked" : ""} /> Multi-panel sheet</label>
    <label class="check"><input type="checkbox" data-bind="subjects.${index}.audioReuse" ${subject.audioReuse ? "checked" : ""} /> Reuse the audio words</label>
    ${field("Accent", `<select data-bind="subjects.${index}.accent">${opt(accents, subject.accent || "", (v) => v || "none")}</select>`)}
  </div>
  <label>Audio transcript <textarea data-bind="subjects.${index}.transcript" placeholder="Original words, kept out of the prompt unless reuse is on.">${esc(subject.transcript || "")}</textarea></label>
  <button type="button" data-library-add="${index}">Save to library</button>`;
}

function shotSlot(clip, shot, index) {
  const verbs = S.banks.moveVerbs || [];
  const parts = shot.moveParts || { verb: "hold", amplitude: "", speed: "", landing: "" };
  const beats = [""].concat(S.banks.beats || []);
  const ready = Object.keys(S.banks.readyLines || {});
  return `<details ${shot.folded ? "" : "open"}>
    <summary>Move, face, sign</summary>
    <div class="grid">
      ${field("Beat", `<select data-beat="${index}">${opt(beats, shot.beat || "", (v) => v || "custom")}</select>`)}
      ${field("Verb", `<select data-bind="shots.${index}.moveParts.verb">${opt(verbs.map((v) => v.id), parts.verb || "hold")}</select>`)}
      ${field("Amplitude", `<select data-bind="shots.${index}.moveParts.amplitude">${opt(["", "small", "large"], parts.amplitude || "", (v) => v || "omit")}</select>`)}
      ${field("Speed", `<select data-bind="shots.${index}.moveParts.speed">${opt(["", "slow", "fast"], parts.speed || "", (v) => v || "omit")}</select>`)}
    </div>
    <label>Landing <input data-bind="shots.${index}.moveParts.landing" value="${esc(parts.landing || "")}" placeholder="toward her face" /></label>
    <button type="button" data-build-move="${index}">Write the move phrase</button>
    <label class="check"><input type="checkbox" data-bind="shots.${index}.locked" ${shot.locked ? "checked" : ""} /> Lock this shot against a draft</label>
    <div class="grid">
      ${field("Eyeline", `<select data-bind="shots.${index}.eyeline">${opt(["", "Eyes stay toward frame-left, off the lens", "Eyes stay toward frame-right, off the lens", "Eyes stay on the lens", "Eyes stay on the other person, off the lens"], shot.eyeline || "", (v) => v || "unset")}</select>`)}
      ${field("Expression", `<input data-bind="shots.${index}.expression" value="${esc(shot.expression || "")}" placeholder="Her brows sit level." />`)}
    </div>
    <label>Sign <input data-bind="shots.${index}.onScreenText" value="${esc(shot.onScreenText || "")}" placeholder="ಕೇಂದ್ರ ಕಾರಾಗೃಹ" /></label>
    <label class="check"><input type="checkbox" data-bind="shots.${index}.onScreenReadable" ${shot.onScreenReadable !== false ? "checked" : ""} /> The sign is readable</label>
    <label>Sound the characters can hear <input data-bind="shots.${index}.diegetic" value="${esc(shot.diegetic || "")}" placeholder="A radio plays in the next room." /></label>
    ${ready.length ? `<label>Ready line <span class="bar"><select data-ready="${index}">${opt([""].concat(ready), "", (v) => v || "choose")}</select></span></label>` : ""}
  </details>`;
}

function soundSlot(clip) {
  const shots = clip.shots || [];
  const dur = Number(clip.durationSec) || 1;
  const starts = shots.map((s, i) => i === 0 ? 0 : Number(s.startSec) || 0);
  const bar = shots.map((s, i) => {
    const end = i + 1 < shots.length ? starts[i + 1] : dur;
    const width = Math.max(8, ((end - starts[i]) / dur) * 100);
    return `<div class="seg" style="flex:${width}">${i + 1}</div>`;
  }).join("");
  const pics = [];
  (clip.subjects || []).forEach((s) => pics.push(s.imageLabel));
  (clip.extras || []).forEach((s) => pics.push(s.label));
  const order = [...new Set(pics.filter((n) => n != null))].sort((a, b) => a - b).map((n) =>
    `<span class="bar"><b>Picture ${esc(n)}</b><button type="button" data-swap="${esc(n)}" data-dir="-1">Up</button><button type="button" data-swap="${esc(n)}" data-dir="1">Down</button></span>`
  ).join("");
  return `<section class="card" id="sec-timeline">
    <h2>Timeline</h2>
    <div class="timeline" title="Shot lengths inside the clip">${bar}</div>
    <button type="button" data-fix="reflow">Reflow cuts to the spoken length</button>
    ${order ? `<h2>Upload order</h2><div class="stack">${order}</div>` : ""}
    ${clip.audioPolicy === "full" ? `<div class="grid">
      <label>Ambience <textarea data-bind="ambience">${esc(clip.ambience || "")}</textarea></label>
      <label>Foley <textarea data-bind="foley">${esc(clip.foley || "")}</textarea></label>
      <label>Non-verbal <textarea data-bind="humanSounds">${esc(clip.humanSounds || "")}</textarea></label>
    </div>` : ""}
  </section>`;
}

function altView() {
  if (S.view === "episode") return episodeView();
  if (S.view === "library") return libraryView();
  if (S.view === "dashboard") return `<section class="card"><h2>All checks</h2><div id="dash">Looking…</div></section>`;
  if (S.view === "sheets") return sheetsView();
  return "";
}

function episodeView() {
  const clips = (S.project.clips || []).filter((c) => !c.variantOf);
  let total = 0;
  const rows = clips.map((c, i) => {
    total += Number(c.durationSec) || 0;
    return `<tr><td>${i + 1}</td><td><button type="button" data-pick="${esc(c.id)}">${esc(c.title || "Untitled")}</button></td><td>${esc(c.mode)}</td><td>${esc(c.durationSec)}s</td><td>${esc(c.status || "draft")}</td></tr>`;
  }).join("");
  return `<section class="card"><h2>Episode · ${total}s</h2>
    <table><thead><tr><th>#</th><th>Title</th><th>Mode</th><th>Duration</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="bar"><button type="button" id="link-neighbors">Link neighbors</button><button type="button" id="back-editor">Back to the clip</button></div>
  </section>`;
}

function libraryView() {
  const cast = ((S.project.library || {}).cast) || [];
  const locations = ((S.project.library || {}).locations) || [];
  const card = (row, kind) => `<div class="row"><b>${esc(row.name)}</b> <span class="hint">${esc(row.voiceId || row.kind || "")}</span>
    <button type="button" data-use-lib="${esc(kind)}" data-id="${esc(row.id)}">Use in this clip</button></div>`;
  return `<section class="card"><h2>Library</h2>
    <h2>People</h2>${cast.map((r) => card(r, "cast")).join("") || `<p class="hint">Save a subject from a clip.</p>`}
    <h2>Locations</h2>${locations.map((r) => card(r, "locations")).join("") || `<p class="hint">No locations yet.</p>`}
    <label>New location <span class="bar"><input id="loc-name" placeholder="station office" /><input id="loc-wall" placeholder="north wall" /><button type="button" id="add-loc">Add</button></span></label>
    <button type="button" id="back-editor">Back to the clip</button>
  </section>`;
}

function sheetsView() {
  const names = S.sheetNames || [];
  return `<section class="card"><h2>Cheatsheets</h2>
    <label>Sheet <select id="sheet-pick">${names.map((n) => `<option>${esc(n)}</option>`).join("")}</select></label>
    <pre class="sheet" id="sheet-body">${esc(S.sheetText || "Choose a sheet.")}</pre>
    <div class="bar"><button type="button" id="reload-rules">Rebuild rules from the workbook</button><button type="button" id="back-editor">Back</button></div>
    <h2>Custom style</h2>
    <div class="grid">
      <label>Id <input id="style-id" placeholder="courtroom" /></label>
      <label>Opening <input id="style-opening" /></label>
    </div>
    <label>Notes <textarea id="style-notes"></textarea></label>
    <button type="button" id="save-style">Save style</button>
  </section>`;
}

document.addEventListener("pointerdown", (ev) => {
  const t = ev.target.closest("button, select, input, textarea");
  if (!t) return;
  if (t.id === "act-undo" || t.id === "act-redo") return;
  if (!S._armed) {
    pushUndo();
    S._armed = true;
    setTimeout(() => { S._armed = false; }, 400);
  }
}, true);

document.addEventListener("click", async (ev) => {
  const t = ev.target.closest("button, [data-mode]");
  if (!t) return;
  if (t.dataset.mode && t.dataset.mode !== "settings") S.view = "editor";
  const id = t.id;
  if (id === "act-undo") return undo();
  if (id === "act-redo") return redo();
  if (id === "act-episode") { S.view = "episode"; paint(); return; }
  if (id === "act-library") { S.view = "library"; paint(); return; }
  if (id === "act-dashboard") { S.view = "dashboard"; paint(); loadDash(); return; }
  if (id === "act-sheets") { S.view = "sheets"; paint(); loadSheets(); return; }
  if (id === "act-palette") return commandPalette();
  if (id === "back-editor") { S.view = "editor"; paint(); return; }
  if (id === "add-scene") return addScene();
  if (id === "rename-scene") return renameScene();
  if (id === "apply-template") return applyTemplate();
  if (id === "dup-clip") return dup(false);
  if (id === "var-clip") return dup(true);
  if (id === "split-clip") return split();
  if (id === "merge-clip") return mergeNext();
  if (id === "link-neighbors") return linkNeighbors();
  if (id === "remove-clip") {
    const c = clip();
    if (!c || !confirm("Remove " + (c.title || "this clip") + "?")) return;
    S.project.clips = S.project.clips.filter((x) => x.id !== c.id);
    (S.project.scenes || []).forEach((s) => { s.clipIds = (s.clipIds || []).filter((id) => id !== c.id); });
    S.clipId = (visibleClips()[0] && visibleClips()[0].id) || null;
    paint();
    saveLocal();
    return;
  }
  if (id === "probe-files") return probeFiles();
  if (id === "act-payload") return downloadPayload();
  if (id === "act-review-draft" || id === "act-apply-draft") return reviewDraft();
  if (id === "apply-sections") return applySections();
  if (id === "drop-review") { S.review = null; paint(); return; }
  if (id === "continue-next") return continueNext();
  if (id === "add-loc") return addLocation();
  if (id === "reload-rules") return rebuildRules();
  if (id === "save-style") return saveStyle();
  if (t.dataset.fix) return runFix(t.dataset.fix);
  if (t.dataset.buildMove != null) return buildMove(Number(t.dataset.buildMove));
  if (t.dataset.swap) return swapPic(Number(t.dataset.swap), Number(t.dataset.dir));
  if (t.dataset.libraryAdd != null) return saveSubject(Number(t.dataset.libraryAdd));
  if (t.dataset.useLib) return useLibrary(t.dataset.useLib, t.dataset.id);
}, true);

document.addEventListener("change", async (ev) => {
  const t = ev.target;
  if (t.id === "scene-pick") {
    S.sceneId = t.value;
    ensureClip();
    paint();
    saveLocal();
  }
  if (t.id === "only-errors") {
    S.onlyErrors = t.checked;
    paint();
  }
  if (t.id === "sheet-pick") {
    const data = await api("/api/sheets?name=" + encodeURIComponent(t.value));
    S.sheetText = data.text;
    const body = document.getElementById("sheet-body");
    if (body) body.textContent = data.text;
  }
  if (t.dataset.beat != null && t.value) {
    const clip = window.clip();
    const data = await api("/api/studio", { action: "move", beat: t.value, clip });
    const shot = clip.shots[Number(t.dataset.beat)];
    shot.beat = t.value;
    shot.moveParts = data.parts;
    shot.cameraMove = data.phrase;
    paint();
    touch();
  }
  if (t.dataset.ready != null && t.value) {
    const clip = window.clip();
    const line = (clip.shots[Number(t.dataset.ready)].lines || [])[0];
    const table = (S.banks.readyLines || {})[t.value] || {};
    if (line) {
      const lang = line.language || "Kannada";
      if (table[lang]) line.native = table[lang];
    } else {
      clip.shots[Number(t.dataset.ready)].text = (clip.shots[Number(t.dataset.ready)].text || "") + " " + t.value;
    }
    paint();
    touch();
  }
});

document.addEventListener("input", (ev) => {
  if (ev.target.id === "clip-find") {
    S.query = ev.target.value;
    ensureClip();
    const list = document.getElementById("clip-list");
    if (list) list.innerHTML = visibleClips().map(clipRow).join("") || `<p class="empty">No clips match.</p>`;
  }
});

document.addEventListener("keydown", (ev) => {
  const meta = ev.ctrlKey || ev.metaKey;
  if (meta && ev.key === "z" && !ev.shiftKey) { ev.preventDefault(); undo(); }
  else if (meta && (ev.key === "Z" || (ev.key === "z" && ev.shiftKey) || ev.key === "y")) { ev.preventDefault(); redo(); }
  else if (meta && ev.key === "s") { ev.preventDefault(); document.getElementById("act-save-disk")?.click(); }
  else if (meta && ev.key === "k") { ev.preventDefault(); commandPalette(); }
  else if (ev.altKey && ev.key === "n") { ev.preventDefault(); document.getElementById("add-shot")?.click(); }
  else if (ev.altKey && ev.key === "ArrowDown") { ev.preventDefault(); stepClip(1); }
  else if (ev.altKey && ev.key === "ArrowUp") { ev.preventDefault(); stepClip(-1); }
});

document.addEventListener("dragover", (ev) => {
  if (ev.dataTransfer && [...ev.dataTransfer.types].includes("Files")) ev.preventDefault();
});
document.addEventListener("drop", async (ev) => {
  const card = ev.target.closest("[data-bind], label");
  if (!card || !ev.dataTransfer.files.length) return;
  ev.preventDefault();
  const file = ev.dataTransfer.files[0];
  const data = await file.arrayBuffer();
  const bytes = new Uint8Array(data);
  let binary = "";
  bytes.forEach((b) => { binary += String.fromCharCode(b); });
  const saved = await api("/api/studio", { action: "media", name: file.name, data: btoa(binary) });
  const input = card.querySelector("[data-bind]") || document.querySelector("[data-bind$='imageFile']");
  if (input) {
    input.value = saved.path;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
});

function undo() {
  if (!S.undoStack.length) return;
  S.redoStack.push(JSON.stringify(S.project));
  restore(S.undoStack.pop());
}
function redo() {
  if (!S.redoStack.length) return;
  S.undoStack.push(JSON.stringify(S.project));
  restore(S.redoStack.pop());
}
function stepClip(dir) {
  const list = visibleClips();
  const i = list.findIndex((c) => c.id === S.clipId);
  const next = list[i + dir];
  if (next) selectClip(next.id);
}

async function runFix(fix) {
  const c = clip();
  if (!c) return;
  const data = await api("/api/studio", { action: "fix", fix, clip: c });
  replaceClip(data.clip);
}
async function buildMove(index) {
  const c = clip();
  const shot = c.shots[index];
  const data = await api("/api/studio", { action: "move", parts: shot.moveParts, clip: c });
  shot.cameraMove = data.phrase;
  paint();
  touch();
}
async function swapPic(label, direction) {
  const data = await api("/api/studio", { action: "swap", clip: clip(), label, direction });
  replaceClip(data.clip);
}
function replaceClip(next) {
  const i = S.project.clips.findIndex((c) => c.id === next.id);
  if (i >= 0) S.project.clips[i] = next;
  S.clipId = next.id;
  paint();
  scheduleAssemble();
  saveLocal();
  S.dirty = true;
}
async function applyTemplate() {
  const name = document.getElementById("template-name").value;
  const data = await api("/api/studio", { action: "template", name, clip: clip() });
  replaceClip(data.clip);
}
async function dup(variant) {
  const data = await api("/api/studio", { action: "duplicate", clip: clip(), variant });
  S.project.clips.push(data.clip);
  remember(data.clip);
  S.clipId = data.clip.id;
  paint();
  saveLocal();
}
async function split() {
  if ((clip().shots || []).length < 2) { alert("Add a second shot before splitting."); return; }
  const data = await api("/api/studio", { action: "split", clip: clip(), at: 1 });
  const [left, right] = data.clips;
  const i = S.project.clips.findIndex((c) => c.id === clip().id);
  S.project.clips.splice(i, 1, left, right);
  remember(left); remember(right);
  S.clipId = left.id;
  paint();
  saveLocal();
}
async function mergeNext() {
  const list = S.project.clips.filter((c) => !c.variantOf && (c.sceneId || "sc-default") === (clip().sceneId || "sc-default"));
  const i = list.findIndex((c) => c.id === clip().id);
  if (!list[i + 1]) return alert("There is no next clip in this scene.");
  const data = await api("/api/studio", { action: "merge", left: list[i], right: list[i + 1] });
  S.project.clips = S.project.clips.filter((c) => c.id !== list[i].id && c.id !== list[i + 1].id);
  S.project.clips.splice(i, 0, data.clip);
  remember(data.clip);
  S.clipId = data.clip.id;
  paint();
  saveLocal();
}
function remember(c) {
  const scene = (S.project.scenes || []).find((s) => s.id === (c.sceneId || S.sceneId));
  if (scene && !scene.clipIds.includes(c.id)) scene.clipIds.push(c.id);
}
async function linkNeighbors() {
  const data = await api("/api/studio", { action: "link", clips: S.project.clips });
  S.project.clips = data.clips;
  paint();
  saveLocal();
}
async function probeFiles() {
  const c = clip();
  const paths = [];
  (c.subjects || []).forEach((s) => s.imageFile && paths.push([s, "imageFile", "Picture " + s.imageLabel]));
  (c.extras || []).forEach((s) => s.file && paths.push([s, "file", "Picture " + s.label]));
  (c.videos || []).forEach((s) => s.file && paths.push([s, "file", "Video " + s.label]));
  if (c.frames) {
    if (c.frames.first) paths.push([c.frames, "first", "Opening frame"]);
    if (c.frames.last) paths.push([c.frames, "last", "Closing frame"]);
  }
  const notes = [];
  for (const [obj, key, role] of paths) {
    const info = await api("/api/studio", { action: "probe", path: obj[key], role });
    obj.fileMtime = info.mtime;
    if (info.width) notes.push(`${role}: ${info.width}×${info.height}`);
    if (info.duration != null) notes.push(`${role}: ${info.duration}s`);
    (info.findings || []).forEach((f) => notes.push(f.message));
  }
  c.fileReport = notes.join("\n") || "Nothing to measure.";
  paint();
  touch();
}
function downloadPayload() {
  const blob = new Blob([JSON.stringify(S.payload || {}, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "payload.json";
  a.click();
}
async function reviewDraft() {
  const c = clip();
  if (!c || !c.aiDraft) return alert("There is no AI draft on this clip. Run AI reformat or AI grammar first.");
  const data = await api("/api/studio", { action: "diff", clip: c, draft: c.aiDraft });
  S.review = data.sections || [];
  paint();
}
async function applySections() {
  const c = clip();
  const accept = [...document.querySelectorAll("[data-accept]:checked")].map((box) => box.dataset.accept);
  const data = await api("/api/studio", { action: "apply-draft", clip: c, draft: c.aiDraft, accept });
  S.review = null;
  replaceClip(data.clip);
}
async function continueNext() {
  const data = await api("/api/studio", { action: "continue", clips: S.project.clips, clipId: clip().id });
  S.project.clips = data.clips;
  (S.project.scenes || []).forEach((scene) => {
    data.clips.forEach((c) => {
      if ((c.sceneId || "sc-default") === scene.id && !(scene.clipIds || []).includes(c.id)) scene.clipIds.push(c.id);
    });
  });
  S.clipId = data.clipId;
  paint();
  scheduleAssemble();
  saveLocal();
}
function addScene() {
  const id = "sc" + Math.random().toString(16).slice(2, 8);
  const title = prompt("Scene name", "Scene") || "Scene";
  S.project.scenes.push({ id, title, notes: "", platesComments: "", clipIds: [] });
  S.sceneId = id;
  paint();
  saveLocal();
}
function renameScene() {
  const scene = (S.project.scenes || []).find((s) => s.id === S.sceneId);
  if (!scene) return;
  scene.title = prompt("Scene name", scene.title) || scene.title;
  paint();
  saveLocal();
}
function saveSubject(index) {
  const sub = clip().subjects[index];
  S.project.library = S.project.library || { cast: [], locations: [] };
  const row = { id: sub.libraryId || ("lib" + Math.random().toString(16).slice(2, 8)), name: sub.name, kind: sub.kind, gender: sub.gender, voiceId: sub.voiceId, accent: sub.accent, imageFile: sub.imageFile, description: sub.description };
  sub.libraryId = row.id;
  const list = S.project.library.cast;
  const at = list.findIndex((r) => r.id === row.id);
  if (at >= 0) list[at] = row; else list.push(row);
  saveLocal();
  alert("Saved " + (row.name || "subject") + " to the library.");
}
function useLibrary(kind, id) {
  const c = clip();
  if (!c) return;
  const row = ((S.project.library || {})[kind] || []).find((r) => r.id === id);
  if (!row) return;
  if (kind === "locations") {
    c.endState = ((c.endState || "") + "\n" + row.name + (row.wall ? ", " + row.wall : "")).trim();
  } else {
    const sub = newSubject(c);
    Object.assign(sub, { name: row.name, kind: row.kind || "person", gender: row.gender || "female", voiceId: row.voiceId || "F3", accent: row.accent || "", imageFile: row.imageFile || "", description: row.description || "", libraryId: row.id, speaks: true });
    c.subjects.push(sub);
  }
  S.view = "editor";
  paint();
  touch();
}
function addLocation() {
  const name = document.getElementById("loc-name").value.trim();
  if (!name) return;
  S.project.library = S.project.library || { cast: [], locations: [] };
  S.project.library.locations.push({ id: "loc" + Math.random().toString(16).slice(2, 8), name, wall: document.getElementById("loc-wall").value.trim() });
  paint();
  saveLocal();
}
async function loadDash() {
  const box = document.getElementById("dash");
  if (!box) return;
  const cont = await api("/api/studio", { action: "continuity", clips: S.project.clips });
  const blocks = [];
  for (const c of S.project.clips) {
    const data = await api("/api/assemble", { clip: c });
    const extra = (cont.findings && cont.findings[c.id]) || [];
    const all = (data.findings || []).concat(extra);
    if (!all.length) continue;
    blocks.push(`<h2>${esc(c.title || c.id)}</h2><ul class="val">${all.map((f) => `<li class="${f.severity === "error" ? "err" : "warn"}">${esc(f.id)} ${esc(f.message)}</li>`).join("")}</ul>`);
  }
  box.innerHTML = blocks.join("") || `<p class="hint">No problems in this project.</p>`;
}
async function loadSheets() {
  const data = await api("/api/sheets");
  S.sheetNames = data.sheets;
  if (S.sheetNames[0]) {
    const body = await api("/api/sheets?name=" + encodeURIComponent(S.sheetNames[0]));
    S.sheetText = body.text;
  }
  paint();
}
async function rebuildRules() {
  const data = await api("/api/studio", { action: "rebuild-rules" });
  alert("Rebuilt rules. " + data.rows + " rows. Reload the page to refresh menus.");
}
async function saveStyle() {
  const data = await api("/api/studio", {
    action: "style",
    id: document.getElementById("style-id").value.trim(),
    opening: document.getElementById("style-opening").value.trim(),
    notes: document.getElementById("style-notes").value.trim(),
  });
  alert("Saved " + data.path + ". Reload to see it in the style menu.");
}
function commandPalette() {
  const modal = document.getElementById("modal");
  const commands = [
    ["Episode roll", () => { S.view = "episode"; paint(); }],
    ["Library", () => { S.view = "library"; paint(); }],
    ["All checks", () => { S.view = "dashboard"; paint(); loadDash(); }],
    ["Cheatsheets", () => { S.view = "sheets"; paint(); loadSheets(); }],
    ["Link neighbors", () => linkNeighbors()],
    ["Duplicate clip", () => dup(false)],
    ["Export scene", () => document.getElementById("act-export").click()],
    ["Toggle offline", () => { S.project.ai.offline = !S.project.ai.offline; paint(); saveLocal(); }],
  ];
  modal.className = "modal-bg open";
  modal.innerHTML = `<div class="modal"><h2>Commands</h2><div class="finder">${commands.map((c, i) => `<button type="button" data-cmd="${i}">${esc(c[0])}</button>`).join("")}</div><button type="button" id="cmd-close">Close</button></div>`;
  modal.querySelector(".finder").onclick = (ev) => {
    const b = ev.target.closest("[data-cmd]");
    if (!b) return;
    modal.className = "modal-bg";
    commands[Number(b.dataset.cmd)][1]();
  };
  document.getElementById("cmd-close").onclick = () => { modal.className = "modal-bg"; };
}

function migrateProject() {
  if (!S.project) return;
  S.project.schemaVersion = 2;
  S.project.library = S.project.library || { cast: [], locations: [] };
  S.project.houseAudio = S.project.houseAudio || "dialogue-only";
  if (!S.project.scenes || !S.project.scenes.length) {
    S.project.scenes = [{ id: "sc-default", title: "Scene 1", notes: "", platesComments: "", clipIds: (S.project.clips || []).map((c) => c.id) }];
  }
  const known = new Set(S.project.scenes.flatMap((s) => s.clipIds || []));
  (S.project.clips || []).forEach((c) => {
    c.sceneId = c.sceneId || "sc-default";
    c.status = c.status || "draft";
    c.clipKind = c.clipKind || "narrative";
    if (c.autoTasks == null) c.autoTasks = true;
    (c.shots || []).forEach((s) => {
      s.moveParts = s.moveParts || { verb: "hold", amplitude: "", speed: "", landing: "" };
    });
    (c.subjects || []).forEach((s) => {
      if (s.identityLock == null) s.identityLock = false;
      if (s.identityOnly == null) s.identityOnly = false;
    });
    if (!known.has(c.id)) {
      S.project.scenes[0].clipIds.push(c.id);
      known.add(c.id);
    }
  });
  S.sceneId = S.sceneId || S.project.scenes[0].id;
}

const _removeThing = removeThing;
removeThing = function (kind, t) {
  if ((kind === "subject" || kind === "shot") && !confirm("Remove this " + kind + "?")) return;
  _removeThing(kind, t);
};

setTimeout(function waitProject() {
  if (!S.project) { setTimeout(waitProject, 40); return; }
  migrateProject();
  paint();
}, 40);
