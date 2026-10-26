/* h3-mechanic editor. The prompt text is assembled by the Python engine. */

const MODES = [
  ["t2va", "T2VA"],
  ["i2va", "I2VA"],
  ["fl2va", "FL2VA"],
  ["l2va", "L2VA"],
  ["ref2va", "Ref2VA"],
  ["settings", "Settings"],
];

const S = {
  project: null,
  banks: null,
  mode: "ref2va",
  clipId: null,
  prompt: "",
  findings: [],
  attach: [],
  speakers: {},
  keys: {},
  models: {},
  struct: 0,
};

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[c]));
const uid = (p) => p + Math.random().toString(16).slice(2, 10);

async function api(path, body) {
  const res = await fetch(path, body == null ? undefined : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function clip() {
  return (S.project.clips || []).find((c) => c.id === S.clipId) || null;
}
function visibleClips() {
  return S.project.clips.filter((c) => c.mode === S.mode);
}
function voicePhrase(id) {
  const row = (S.banks.voices || []).find((v) => v.id === id);
  return row ? row.phrase : "";
}
function tip(snippet, example) {
  return esc([snippet, example].filter(Boolean).join(" — "));
}

function applyAppearance(a) {
  a = a || {};
  document.documentElement.dataset.theme = a.theme || "light";
  document.documentElement.dataset.accent = a.accent || "blue";
  document.documentElement.style.setProperty("--ui-scale", a.fontScale || "1");
  if (a.scriptFont) document.documentElement.style.setProperty("--script-font", a.scriptFont);
  else document.documentElement.style.removeProperty("--script-font");
  localStorage.setItem("h3m:appearance", JSON.stringify(a));
}

function saveLocal() {
  localStorage.setItem("h3m:project", JSON.stringify(S.project));
  localStorage.setItem("h3m:mode", S.mode);
  localStorage.setItem("h3m:clip", S.clipId || "");
}

let saveTimer = 0;
function touch() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveLocal, 200);
  scheduleAssemble();
}

let asmTimer = 0;
function scheduleAssemble() {
  clearTimeout(asmTimer);
  asmTimer = setTimeout(assembleActive, 160);
}

async function assembleActive() {
  const c = clip();
  if (!c || S.mode === "settings") {
    paintPreview();
    return;
  }
  try {
    const data = await api("/api/assemble", { clip: c });
    S.prompt = data.body || "";
    S.findings = data.findings || [];
    S.attach = data.attach || [];
    S.speakers = data.speakers || {};
    S.words = data.words || 0;
    S.payload = data.payload || null;
  } catch (err) {
    S.findings = [{ id: "net", severity: "error", message: err.message, focus: "preview" }];
  }
  paintPreview();
  paintClipMarks();
}

function newShot(index, duration) {
  const start = index === 1 ? null : Math.min(Math.max(duration - 1, 1), 3 * (index - 1));
  return {
    size: "medium close-up", angle: "front", lens: "85mm",
    cameraMove: "holds a static shot", cameraKey: "",
    startSec: start, text: "", custom: false, offscreenGuard: false, lines: [],
  };
}
function usedLabels(c) {
  const set = new Set();
  (c.subjects || []).forEach((s) => set.add(Number(s.imageLabel)));
  (c.extras || []).forEach((s) => set.add(Number(s.label)));
  (c.videos || []).forEach((s) => set.add(Number(s.label)));
  return set;
}
function nextFree(c) {
  const set = usedLabels(c);
  let n = 1;
  while (set.has(n)) n += 1;
  return n;
}
function newSubject(c) {
  return {
    id: uid("s"), name: "", kind: "person", gender: "female", speaks: false,
    imageLabel: nextFree(c), imageFile: "", description: "",
    timbre: "library", voiceId: "F3", customVoice: "", audioLabel: nextFree(c), audioFile: "",
  };
}
function reflow(c) {
  const n = c.shots.length || 1;
  const dur = Number(c.durationSec) || 8;
  c.shots.forEach((s, i) => {
    s.startSec = i === 0 ? null : Math.round((dur * i / n) * 10) / 10;
  });
}
function styleOpening(id) {
  const row = (S.banks.styles || []).find((s) => s.id === id);
  return row ? row.opening : "";
}

function selectClip(id) {
  S.clipId = id;
  const c = clip();
  if (c) S.mode = c.mode;
  paint();
  assembleActive();
}

function ensureClip() {
  const list = visibleClips();
  if (!list.length) {
    S.clipId = null;
    return;
  }
  if (!list.some((c) => c.id === S.clipId)) S.clipId = list[0].id;
}

/* ---------- paint ---------- */

function paint() {
  paintHeader();
  paintTabs();
  if (S.mode === "settings") {
    paintSettings();
    if (!S._ollamaAsked) {
      S._ollamaAsked = true;
      refreshModels("ollama");
    }
  } else paintEditorShell();
  S.struct += 1;
}

function paintHeader() {
  $("#project-title").value = S.project.title || "";
  $("#header-actions").innerHTML = `
    <button type="button" id="act-save">Save</button>
    <button type="button" id="act-save-disk">Save to disk</button>
    <button type="button" id="act-open">Open</button>
    <button type="button" id="act-export">Export scene</button>
    <button type="button" id="act-import-scene">Import scene</button>
  `;
}

function paintTabs() {
  $("#tabs").innerHTML = MODES.map(([id, label]) =>
    `<button type="button" data-mode="${id}" class="${id === S.mode ? "primary" : ""}" aria-current="${id === S.mode ? "page" : "false"}">${label}</button>`
  ).join("");
}

function paintEditorShell() {
  ensureClip();
  const list = visibleClips();
  $("#app").innerHTML = `<div class="shell">
    <div class="col" id="rail">
      <section class="card">
        <h2>${esc(S.mode.toUpperCase())} clips</h2>
        ${slot("rail")}
        <div class="stack" id="clip-list">${list.map(clipRow).join("") || `<p class="empty">No ${esc(S.mode.toUpperCase())} clips yet.</p>`}</div>
        <button type="button" class="primary" id="add-clip">Add clip</button>
      </section>
    </div>
    <div class="col" id="editor">${clip() ? editorHTML(clip()) : `<section class="card"><p class="empty">Add a clip to start a prompt.</p></section>`}</div>
    <div class="col" id="side">${previewHTML()}</div>
  </div>`;
  paintPreview();
}

function clipRow(c) {
  const err = S._marks && S._marks[c.id];
  return `<div class="bar" draggable="true" data-drop="clip" data-id="${esc(c.id)}">
    <button type="button" class="clip-btn ${c.id === S.clipId ? "primary" : ""}" data-pick="${esc(c.id)}">
      <span>${esc(c.title || "Untitled")}</span>
      <small>${esc(c.durationSec)}s ${err ? `<i class="dot" title="Has an error"></i>` : ""}</small>
    </button>
  </div>`;
}

function paintClipMarks() {
  const marks = {};
  if (clip()) marks[clip().id] = S.findings.some((f) => f.severity === "error");
  S._marks = Object.assign(S._marks || {}, marks);
  document.querySelectorAll("[data-pick]").forEach((btn) => {
    const id = btn.dataset.pick;
    const small = btn.querySelector("small");
    if (!small) return;
    const c = S.project.clips.find((x) => x.id === id);
    if (!c) return;
    small.innerHTML = `${esc(c.durationSec)}s ${S._marks[id] ? `<i class="dot" title="Has an error"></i>` : ""}`;
  });
}

function field(label, inner, title) {
  return `<label ${title ? `title="${title}"` : ""}>${label}${inner}</label>`;
}
function opt(list, current, labels) {
  return list.map((v) => {
    const text = labels ? labels(v) : (v === "" ? "none" : v);
    return `<option value="${esc(v)}" ${String(v) === String(current) ? "selected" : ""}>${esc(text)}</option>`;
  }).join("");
}

function slot(name, ...args) {
  try { return (window.h3Slot && window.h3Slot(name, ...args)) || ""; }
  catch { return ""; }
}

function editorHTML(c) {
  const ref = c.mode === "ref2va";
  const frame = c.mode === "i2va" || c.mode === "fl2va" || c.mode === "l2va";
  return `
    ${metaHTML(c)}
    ${slot("after-meta", c)}
    ${frame ? framesHTML(c) : ""}
    ${castHTML(c, ref)}
    ${ref ? extrasHTML(c) + anchorsHTML(c) + videosHTML(c) + summaryHTML(c) + retentionHTML(c) : ""}
    ${shotsHTML(c)}
    ${slot("before-sound", c)}
    ${soundHTML(c)}
    <section class="card" id="sec-notes">
      <h2>Notes</h2>
      <label>Import leftovers and private notes
        <textarea data-bind="notes">${esc(c.notes || "")}</textarea>
      </label>
    </section>`;
}

function metaHTML(c) {
  const ratios = c.mode === "t2va" ? S.banks.ratios
    : c.mode === "ref2va" ? ["adaptive", ...S.banks.ratios]
    : ["adaptive"];
  const res = c.model === "H3-Max" ? ["480P", "768P"] : ["768P", "2K"];
  const durMin = c.model === "H3-Max" ? 5 : 4;
  return `<section class="card" id="sec-meta">
    <h2>Clip</h2>
    <div class="grid">
      ${field("Title", `<input data-bind="title" value="${esc(c.title)}" />`)}
      ${field("Mode", `<select data-bind="mode">${opt(MODES.filter(m => m[0] !== "settings").map(m => m[0]), c.mode, (id) => id.toUpperCase())}</select>`)}
      ${field("Model", `<select data-bind="model">${opt(["H3", "H3-Max"], c.model)}</select>`, "H3 is 4–15 s at 768P or 2K. H3-Max is 5–15 s at 480P or 768P.")}
      ${field("Duration (s)", `<input data-bind="durationSec" type="number" min="${durMin}" max="15" value="${esc(c.durationSec)}" />`)}
      ${field("Resolution", `<select data-bind="resolution">${opt(res, c.resolution)}</select>`)}
      ${field("Ratio", `<select data-bind="ratio" ${c.mode !== "t2va" && c.mode !== "ref2va" ? "disabled" : ""}>${opt(ratios, c.ratio)}</select>`, c.mode === "t2va" ? "T2VA needs a concrete ratio." : "Frame modes follow the image.")}
      ${field("Style", `<select data-bind="style">${opt(S.banks.styles.map(s => s.id), c.style)}</select>`)}
      ${field("Audio", `<select data-bind="audioPolicy">${opt(["dialogue-only", "full"], c.audioPolicy, (v) => v === "full" ? "Designed sound" : "Dialogue only")}</select>`, "Dialogue only writes N/A for soundscape and music, and adds the house-audio sentence.")}
    </div>
    <label class="section-gap">Style opening
      <textarea data-bind="styleOpening">${esc(c.styleOpening || "")}</textarea>
    </label>
    <div class="grid section-gap">
      ${field("handoff-from", `<input data-bind="headers.handoffFrom" value="${esc(c.headers.handoffFrom || "")}" />`, "Written at the top of the exported file. Copy skips it.")}
      ${field("end-frame", `<input data-bind="headers.endFrame" value="${esc(c.headers.endFrame || "")}" />`)}
      ${field("next", `<input data-bind="headers.next" value="${esc(c.headers.next || "")}" />`)}
    </div>
  </section>`;
}

function framesHTML(c) {
  const f = c.frames || { first: "", last: "" };
  const showFirst = c.mode === "i2va" || c.mode === "fl2va";
  const showLast = c.mode === "l2va" || c.mode === "fl2va";
  return `<section class="card" id="sec-frames">
    <h2>Frames</h2>
    <p class="hint">These files are the exact frames. They are not character references.</p>
    <div class="grid">
      ${showFirst ? field("Opening frame", pathInput("frames.first", f.first)) : ""}
      ${showLast ? field("Closing frame", pathInput("frames.last", f.last)) : ""}
    </div>
  </section>`;
}

function pathInput(bind, value) {
  return `<span class="bar"><input class="grow" data-bind="${bind}" value="${esc(value || "")}" placeholder="/path/to/file" /><button type="button" data-browse="${bind}">Browse</button></span>`;
}

function castHTML(c, ref) {
  const cards = (c.subjects || []).map((s, i) => subjectCard(c, s, i, ref)).join("");
  return `<section class="card" id="sec-cast">
    <h2>${ref ? "Subjects" : "Cast"}</h2>
    <p class="hint">${ref
      ? "Each person, outfit, location, or prop. Numbers follow this list."
      : "People already in the frame or described in the text. No separate character image."}</p>
    <div id="subjects">${cards}</div>
    <button type="button" id="add-subject">Add ${ref ? "subject" : "person"}</button>
  </section>`;
}

function subjectCard(c, s, i, ref) {
  const speaker = S.speakers[s.id] ? ` · ${S.speakers[s.id]}` : "";
  const timbreHidden = s.speaks ? "" : "hidden";
  return `<div class="row" draggable="true" data-drop="subject" data-index="${i}">
    <div class="row-head"><b>${ref ? `&lt;Subject ${i + 1}&gt;` : "Person"} ${esc(s.name)}<span class="spk" data-sid="${esc(s.id)}">${esc(speaker)}</span></b>
      <span class="bar">
        <button type="button" data-move="subject" data-dir="-1" data-index="${i}" aria-label="Move up">Up</button>
        <button type="button" data-move="subject" data-dir="1" data-index="${i}" aria-label="Move down">Down</button>
        <button type="button" data-remove="subject" data-index="${i}">Remove</button>
      </span>
    </div>
    <div class="grid">
      ${field("Name", `<input data-bind="subjects.${i}.name" value="${esc(s.name)}" />`)}
      ${field("Kind", `<select data-bind="subjects.${i}.kind">${opt(["person", "outfit", "location", "prop"], s.kind)}</select>`)}
      ${field("Gender", `<select data-bind="subjects.${i}.gender">${opt(["female", "male", "unspecified"], s.gender)}</select>`)}
      ${ref ? field("Picture label", `<input data-bind="subjects.${i}.imageLabel" type="number" min="1" value="${esc(s.imageLabel)}" />`) : ""}
    </div>
    ${ref ? `<label>Source file ${pathInput(`subjects.${i}.imageFile`, s.imageFile)}</label>` : ""}
    ${slot("subject", c, s, i)}
    <label>Description <span class="hint">Leave empty to use the standard identity line.</span>
      <textarea data-bind="subjects.${i}.description">${esc(s.description || "")}</textarea>
    </label>
    <label class="check"><input type="checkbox" data-bind="subjects.${i}.speaks" ${s.speaks ? "checked" : ""} /> This person speaks</label>
    <div class="timbre grid" ${timbreHidden}>
      ${field("Timbre", `<select data-bind="subjects.${i}.timbre">${opt(["library", "audio", "custom"], s.timbre, (v) => ({ library: "Library voice", audio: "Audio file", custom: "Custom phrase" }[v]))}</select>`)}
      ${field("Library voice", `<select data-bind="subjects.${i}.voiceId" title="${tip(voicePhrase(s.voiceId), "")}">${(S.banks.voices || []).map((v) => `<option value="${esc(v.id)}" ${v.id === s.voiceId ? "selected" : ""} title="${tip(v.phrase, v.example)}">${esc(v.keyword)}</option>`).join("")}</select>`)}
      <p class="hint voice-phrase">${esc(s.timbre === "custom" ? s.customVoice : s.timbre === "audio" ? `in the voice of <Audio ${s.audioLabel || 1}>` : voicePhrase(s.voiceId))}</p>
      ${field("Custom phrase", `<input data-bind="subjects.${i}.customVoice" value="${esc(s.customVoice || "")}" />`)}
      ${field("Audio label", `<input data-bind="subjects.${i}.audioLabel" type="number" min="1" value="${esc(s.audioLabel || 1)}" />`)}
      <label>Audio file ${pathInput(`subjects.${i}.audioFile`, s.audioFile)}</label>
    </div>
  </div>`;
}

function extrasHTML(c) {
  const rows = (c.extras || []).map((e, i) => `<div class="row">
    <div class="row-head"><b>&lt;Picture ${esc(e.label)}&gt; attribute</b>
      <button type="button" data-remove="extra" data-index="${i}">Remove</button></div>
    <div class="grid">
      ${field("Label", `<input data-bind="extras.${i}.label" type="number" min="1" value="${esc(e.label)}" />`)}
      ${field("Marker", `<select data-bind="extras.${i}.marker">${opt(S.banks.visualMarkers, e.marker || "attribute_transfer")}</select>`)}
    </div>
    <label>File ${pathInput(`extras.${i}.file`, e.file)}</label>
    <label>What it shows <span class="hint">A tattoo, a mark, a layer the costume covers.</span>
      <textarea data-bind="extras.${i}.description">${esc(e.description || "")}</textarea></label>
  </div>`).join("");
  return `<section class="card" id="sec-pictures">
    <h2>Extra pictures</h2>
    <p class="hint">Hidden attributes. Not a new person.</p>
    ${rows}
    <button type="button" id="add-extra">Add picture</button>
  </section>`;
}

function anchorsHTML(c) {
  const pics = pictureChoices(c);
  const shotNs = (c.shots || []).map((_, i) => String(i + 1));
  const rows = (c.anchors || []).map((a, i) => `<div class="row">
    <div class="row-head"><b>Anchor</b><button type="button" data-remove="anchor" data-index="${i}">Remove</button></div>
    <div class="grid">
      ${field("Picture", `<select data-bind="anchors.${i}.imageLabel">${opt(pics, String(a.imageLabel))}</select>`)}
      ${field("Shot", `<select data-bind="anchors.${i}.shot">${opt(shotNs, String(a.shot || 1))}</select>`)}
      ${field("Kind", `<select data-bind="anchors.${i}.kind">${opt(["composition", "keyframe", "end"], a.kind || "composition", (v) => ({ composition: "composition", keyframe: "keyframe", end: "end frame" }[v]))}</select>`)}
    </div>
    <label>Note <input data-bind="anchors.${i}.note" value="${esc(a.note || "")}" /></label>
  </div>`).join("");
  return `<section class="card" id="sec-anchors">
    <h2>Composition anchors</h2>
    <p class="hint">Pins the framing of a shot to a picture you already attached.</p>
    ${rows}
    <button type="button" id="add-anchor">Add anchor</button>
  </section>`;
}

function pictureChoices(c) {
  const set = new Set();
  (c.subjects || []).forEach((s) => set.add(String(s.imageLabel)));
  (c.extras || []).forEach((s) => set.add(String(s.label)));
  return [...set];
}

function videosHTML(c) {
  const rows = (c.videos || []).map((v, i) => `<div class="row">
    <div class="row-head"><b>&lt;Video ${esc(v.label)}&gt;</b>
      <button type="button" data-remove="video" data-index="${i}">Remove</button></div>
    <div class="grid">
      ${field("Label", `<input data-bind="videos.${i}.label" type="number" min="1" value="${esc(v.label)}" />`)}
      ${field("Role", `<input data-bind="videos.${i}.role" value="${esc(v.role || "camera path")}" />`)}
      ${field("Intent", `<select data-bind="videos.${i}.intent">${opt(["camera", "edit", "continuation"], v.intent || "camera")}</select>`)}
    </div>
    <label>File ${pathInput(`videos.${i}.file`, v.file)}</label>
    <label>Description <input data-bind="videos.${i}.description" value="${esc(v.description || "")}" /></label>
  </div>`).join("");
  return `<section class="card" id="sec-videos">
    <h2>Videos</h2>
    ${rows}
    <button type="button" id="add-video">Add video</button>
  </section>`;
}

function summaryHTML(c) {
  const chosen = new Set(c.taskTypes || []);
  const boxes = (S.banks.taskTypes || []).map((t) =>
    `<label class="check"><input type="checkbox" data-task="${esc(t)}" ${chosen.has(t) ? "checked" : ""} /> ${esc(t)}</label>`
  ).join("");
  return `<section class="card" id="sec-summary">
    <h2>Summary</h2>
    <div class="stack">${boxes}</div>
    <label class="section-gap">Paragraph
      <textarea data-bind="summary">${esc(c.summary || "")}</textarea>
    </label>
    <button type="button" id="ai-summary">Draft summary with AI</button>
  </section>`;
}

function retentionHTML(c) {
  const rows = (c.retention || []).map((r, i) => {
    const audio = String(r.label || "").startsWith("<Audio");
    const markers = audio ? S.banks.audioMarkers : S.banks.visualMarkers;
    return `<div class="row">
      <div class="row-head"><b>${esc(r.label)} ${esc(r.context || "")}</b>
        <button type="button" data-remove="retention" data-index="${i}">Remove</button></div>
      <div class="grid">
        ${field("Marker", `<select data-bind="retention.${i}.marker">${opt(markers, r.marker)}</select>`)}
        ${field("Shots", `<input data-bind="retention.${i}.shotsText" value="${esc((r.shots || []).join(", "))}" placeholder="1, 2" />`)}
      </div>
      <label>Note <input data-bind="retention.${i}.note" value="${esc(r.note || "")}" /></label>
    </div>`;
  }).join("");
  return `<section class="card" id="sec-retention">
    <h2>Retention</h2>
    <p class="hint">Speaker ids are not written in this section.</p>
    ${rows}
    <button type="button" id="rebuild-retention">Rebuild from references</button>
  </section>`;
}

function shotsHTML(c) {
  const cards = (c.shots || []).map((shot, i) => shotCard(c, shot, i)).join("");
  return `<section class="card" id="sec-shots">
    <h2>Shots</h2>
    <div id="shots">${cards}</div>
    <button type="button" class="primary" id="add-shot">Add shot</button>
  </section>`;
}

function shotCard(c, shot, i) {
  const cameras = S.banks.cameras || [];
  return `<div class="row" id="shot-${i + 1}" draggable="true" data-drop="shot" data-index="${i}">
    <div class="row-head"><b>Shot ${i + 1}${i ? ` · ${esc(shot.startSec)}s` : ""}</b>
      <span class="bar">
        <button type="button" data-move="shot" data-dir="-1" data-index="${i}">Up</button>
        <button type="button" data-move="shot" data-dir="1" data-index="${i}">Down</button>
        <button type="button" data-remove="shot" data-index="${i}">Remove</button>
      </span>
    </div>
    <div class="grid">
      ${field("Size", `<select data-bind="shots.${i}.size">${opt(S.banks.sizes, shot.size)}</select>`)}
      ${field("Angle", `<select data-bind="shots.${i}.angle">${opt(S.banks.angles, shot.angle)}</select>`)}
      ${field("Lens", `<select data-bind="shots.${i}.lens">${opt(S.banks.lenses, shot.lens, (v) => v || "none")}</select>`)}
      ${i ? field("Start (s)", `<input data-bind="shots.${i}.startSec" type="number" min="0" step="0.1" value="${esc(shot.startSec ?? "")}" />`) : ""}
    </div>
    ${field("Camera move", `<select data-camera="${i}">${[`<option value="">Custom wording</option>`].concat(cameras.map((cam) => `<option value="${esc(cam.keyword)}" ${cam.keyword === shot.cameraKey ? "selected" : ""} title="${tip(cam.snippet, cam.example)}">${esc(cam.keyword)}</option>`)).join("")}</select>`)}
    <label>Move phrase <input data-bind="shots.${i}.cameraMove" value="${esc(shot.cameraMove || "")}" /></label>
    <label>Insert expression
      <select data-expression="${i}"><option value="">Choose a phrase…</option>${(S.banks.expressions || []).map((e) => `<option value="${esc(e.snippet)}" title="${tip(e.snippet, e.example)}">${esc(e.keyword)}</option>`).join("")}</select>
    </label>
    <label class="check"><input type="checkbox" data-bind="shots.${i}.custom" ${shot.custom ? "checked" : ""} /> Use my wording for this shot</label>
    <label class="check"><input type="checkbox" data-bind="shots.${i}.offscreenGuard" ${shot.offscreenGuard ? "checked" : ""} /> No other person appears in the frame</label>
    <label>Action, place, expression
      <textarea data-bind="shots.${i}.text">${esc(shot.text || "")}</textarea>
    </label>
    ${slot("shot", c, shot, i)}
    <h2>Dialogue</h2>
    ${(shot.lines || []).map((line, j) => lineHTML(c, i, j, line)).join("")}
    <button type="button" data-add-line="${i}">Add line</button>
  </div>`;
}

function lineHTML(c, si, j, line) {
  const people = (c.subjects || []).map((s, n) =>
    `<option value="${esc(s.id)}" ${s.id === line.subjectId ? "selected" : ""}>${esc(s.name || (c.mode === "ref2va" ? `Subject ${n + 1}` : "Person"))}</option>`
  ).join("");
  return `<div class="row">
    <div class="row-head"><b>Line</b><button type="button" data-remove="line" data-shot="${si}" data-index="${j}">Remove</button></div>
    <div class="grid">
      ${field("Who", `<select data-bind="shots.${si}.lines.${j}.subjectId">${people}</select>`)}
      ${field("Language", `<select data-bind="shots.${si}.lines.${j}.language">${opt(S.banks.languages, line.language || "English")}</select>`)}
      ${field("Continuation", `<select data-bind="shots.${si}.lines.${j}.continuation">${opt(["", "scenetrans", "cutoff"], line.continuation || "", (v) => ({ "": "none", scenetrans: "continues across the cut", cutoff: "cut off" }[v] || v))}</select>`)}
    </div>
    <label>Spoken words
      <textarea class="native" lang="${esc(line.language || "en")}" data-bind="shots.${si}.lines.${j}.native">${esc(line.native || "")}</textarea>
    </label>
    <label>Delivery <input data-bind="shots.${si}.lines.${j}.delivery" value="${esc(line.delivery || "")}" placeholder="almost a whisper" /></label>
    <label class="check"><input type="checkbox" data-bind="shots.${si}.lines.${j}.voiceover" ${line.voiceover ? "checked" : ""} /> Off-screen voiceover</label>
    <label class="check"><input type="checkbox" data-bind="shots.${si}.lines.${j}.closeMouth" ${line.closeMouth !== false ? "checked" : ""} /> Close the mouth after the line</label>
  </div>`;
}

function soundHTML(c) {
  const off = c.audioPolicy === "dialogue-only";
  return `<section class="card" id="sec-sound">
    <h2>Sound</h2>
    <p class="hint">${off ? "Dialogue only writes N/A for both fields." : "Describe ambience and the score. Music the characters can hear belongs in the shot."}</p>
    <label>Soundscape <textarea data-bind="soundscape" ${off ? "disabled" : ""}>${esc(c.soundscape || "")}</textarea></label>
    <label>Music <textarea data-bind="music" ${off ? "disabled" : ""}>${esc(c.music || "")}</textarea></label>
  </section>`;
}

function previewHTML() {
  return `<section class="card" id="preview">
    <h2>Assembled prompt <span class="hint" id="char-count">0 / 7000</span></h2>
    <p class="hint" id="prompt-meta"></p>
    <div id="draft-wrap" hidden>
      <h2>AI draft</h2>
      <textarea id="ai-draft" readonly></textarea>
      <button type="button" id="clear-draft">Use the assembled prompt</button>
    </div>
    <textarea id="prompt-out" readonly aria-label="Assembled prompt"></textarea>
    <div class="bar">
      <button type="button" id="copy-prompt">Copy</button>
      <button type="button" id="download-prompt">Download</button>
      <button type="button" id="ai-reformat">AI reformat</button>
      <button type="button" id="ai-grammar">AI grammar</button>
    </div>
    <p class="hint" id="ai-who"></p>
  </section>
  <section class="card">
    <h2>Checks</h2>
    <ul class="val" id="validation-list" aria-live="polite"></ul>
  </section>
  <section class="card">
    <h2>Attach order</h2>
    <table id="attach-list"><thead><tr><th>#</th><th>Label</th><th>Role</th><th>File</th></tr></thead><tbody></tbody></table>
  </section>`;
}

function paintPreview() {
  const out = $("#prompt-out");
  if (!out) return;
  const c = clip();
  out.value = S.prompt;
  const n = (S.prompt || "").length;
  const count = $("#char-count");
  count.textContent = `${n} / 7000`;
  count.className = n > 7000 ? "hint err" : "hint";
  const meta = $("#prompt-meta");
  if (c) meta.textContent = `${c.mode.toUpperCase()} · ${c.durationSec}s · ${c.resolution} · ${c.ratio}`;
  const draft = c && c.aiDraft;
  const wrap = $("#draft-wrap");
  if (wrap) {
    wrap.hidden = !draft;
    if (draft) $("#ai-draft").value = draft;
  }
  const list = $("#validation-list");
  if (!S.findings.length) list.innerHTML = `<li class="ok">No problems.</li>`;
  else list.innerHTML = S.findings.map((f) =>
    `<li class="${f.severity === "error" ? "err" : "warn"}" data-focus="${esc(f.focus || "")}"><button type="button" class="linkish" data-focus="${esc(f.focus || "")}">${esc(f.id)}</button> ${esc(f.message)}</li>`
  ).join("");
  const body = document.querySelector("#attach-list tbody");
  if (body) {
    body.innerHTML = (S.attach || []).map((r, i) => `<tr>
      <td>${i + 1}</td>
      <td>${esc(r.kind)} ${esc(r.label)}</td>
      <td>${esc(r.role || "")}</td>
      <td class="${r.missing ? "missing" : ""}">${esc(r.missing ? "MISSING" : r.file)}</td>
    </tr>`).join("") || `<tr><td colspan="4">Nothing to attach.</td></tr>`;
  }
  document.querySelectorAll(".spk").forEach((el) => {
    const id = S.speakers[el.dataset.sid];
    el.textContent = id ? ` · ${id}` : "";
  });
  const who = document.getElementById("ai-who");
  if (who && S.project && S.project.ai) {
    const id = S.project.ai.active || "ollama";
    const model = (S.project.ai[id] && S.project.ai[id].model) || "no model yet";
    who.textContent = S.project.ai.offline
      ? "Offline. The AI buttons are off."
      : `These buttons call ${providerName(id)} · ${model}. Change it under Settings.`;
  }
  const aiOff = S.project.ai && S.project.ai.offline;
  ["ai-reformat", "ai-grammar", "ai-summary"].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = !!aiOff;
  });
}

const AI_PROVIDERS = [
  ["deepseek", "DeepSeek", true],
  ["claude", "Claude", true],
  ["gemini", "Google AI", true],
  ["openai", "OpenAI-compatible", true],
  ["ollama", "Ollama", false],
];

function providerName(id) {
  const row = AI_PROVIDERS.find((p) => p[0] === id);
  return row ? row[1] : id || "none";
}

function loadModelLists() {
  if (S._modelsLoaded) return;
  S._modelsLoaded = true;
  try {
    S.models = Object.assign(JSON.parse(localStorage.getItem("h3m:models") || "{}"), S.models || {});
  } catch {
    S.models = S.models || {};
  }
}

function rememberModels() {
  localStorage.setItem("h3m:models", JSON.stringify(S.models || {}));
}

function paintSettings() {
  loadModelLists();
  const a = S.project.appearance;
  const ai = S.project.ai;
  const providers = AI_PROVIDERS;
  const active = ai.active || "ollama";
  const model = (ai[active] && ai[active].model) || "";
  $("#app").innerHTML = `<section class="card">
      <h2>Which AI the buttons call</h2>
      <p>Reformat, grammar, and draft summary call <b>${esc(providerName(active))}</b>${model ? " · " + esc(model) : ""}. Assembly and the checks never call a provider. Offline turns the buttons off.</p>
      ${field("Active provider", `<select id="active-provider">${opt(providers.map(p => p[0]), active, (id) => providerName(id))}</select>`)}
    </section>
    <div class="shell" style="grid-template-columns: 1fr 1fr">
    <section class="card">
      <h2>Appearance</h2>
      <div class="grid">
        ${field("Theme", `<select data-appear="theme">${opt(["light", "dark", "nord", "nord-light"], a.theme)}</select>`)}
        ${field("Accent", `<select data-appear="accent">${opt(["blue", "pink", "green", "purple"], a.accent)}</select>`)}
        ${field("Font scale", `<select data-appear="fontScale">${opt(["0.9", "1", "1.1", "1.25"], String(a.fontScale), (v) => ({ "0.9": "Small", "1": "Normal", "1.1": "Large", "1.25": "Extra large" }[v]))}</select>`)}
      </div>
      <label>Native-script font
        <input data-appear="scriptFont" value="${esc(a.scriptFont || "")}" placeholder="Noto Sans Kannada, sans-serif" />
      </label>
      <p class="native">ಕನ್ನಡ · हिन्दी · தமிழ்</p>
    </section>
    <section class="card">
      <h2>AI connectivity</h2>
      <label class="check"><input type="checkbox" id="offline" ${ai.offline ? "checked" : ""} /> Offline — assembly and checks only</label>
      ${field("Active provider", `<select id="active-provider">${opt(providers.map(p => p[0]), ai.active, (id) => providers.find(p => p[0] === id)[1])}</select>`)}
      ${providers.map(([id, label, needsKey]) => providerCard(id, label, needsKey)).join("")}
    </section>
  </div>`;
}

function providerCard(id, label, needsKey) {
  const cfg = S.project.ai[id] || { baseUrl: "", model: "" };
  const models = [...(S.models[id] || [])];
  if (cfg.model && !models.includes(cfg.model)) models.unshift(cfg.model);
  const inUse = (S.project.ai.active || "ollama") === id;
  const modelField = models.length
    ? `<select data-provider="${id}" data-key="model">${opt(models, cfg.model)}</select>`
    : `<input data-provider="${id}" data-key="model" value="${esc(cfg.model || "")}" placeholder="Detect or type a model name" />`;
  const status = (S.providerStatus && S.providerStatus[id]) || "";
  return `<div class="row ${inUse ? "in-use" : ""}" id="prov-${id}">
    <div class="row-head"><b>${esc(label)}</b><span class="hint">${inUse ? "used by the AI buttons" : ""} ${S.keys[id] ? "· key saved" : needsKey ? "· no key" : ""}</span></div>
    <label>Host <input data-provider="${id}" data-key="baseUrl" value="${esc(cfg.baseUrl || "")}" /></label>
    <label>Model ${modelField}</label>
    ${needsKey ? `<label>API key <input type="password" data-secret="${id}" placeholder="${S.keys[id] ? "saved — type to replace" : "paste a key"}" autocomplete="off" /></label>` : ""}
    <div class="bar">
      <button type="button" class="${inUse ? "primary" : ""}" data-use-ai="${id}">${inUse ? "In use" : "Use for AI actions"}</button>
      <button type="button" data-test="${id}">Test connection</button>
      <button type="button" data-models="${id}">${id === "ollama" ? "Detect" : "Refresh models"}</button>
      <span class="hint" id="status-${id}">${esc(status)}</span>
    </div>
  </div>`;
}

/* ---------- bind ---------- */

function setBind(bind, value) {
  const c = clip();
  if (!c) return;
  const parts = bind.split(".");
  let obj = c;
  for (let i = 0; i < parts.length - 1; i++) obj = obj[parts[i]];
  const key = parts[parts.length - 1];
  if (key === "shotsText") {
    obj.shots = value.split(/[, ]+/).map((n) => Number(n)).filter((n) => n);
    return;
  }
  if (key === "durationSec" || key === "imageLabel" || key === "audioLabel" || key === "label" || key === "shot") {
    value = Number(value);
  }
  if (key === "startSec") value = value === "" ? null : Number(value);
  obj[key] = value;
  if (key === "style") c.styleOpening = styleOpening(value);
  if (key === "model") {
    if (value === "H3-Max") {
      if (!["480P", "768P"].includes(c.resolution)) c.resolution = "768P";
      if (c.durationSec < 5) c.durationSec = 5;
    } else {
      if (!["768P", "2K"].includes(c.resolution)) c.resolution = "768P";
    }
  }
  if (key === "mode") {
    if (value === "t2va" && c.ratio === "adaptive") c.ratio = "16:9";
    if (value !== "t2va" && value !== "ref2va") c.ratio = "adaptive";
    S.mode = value;
  }
  if (key === "audioPolicy") {
    /* sound fields enable on next paint */
  }
}

document.addEventListener("input", (ev) => {
  const t = ev.target;
  if (t.id === "project-title") {
    S.project.title = t.value;
    touch();
    return;
  }
  if (t.dataset.bind) {
    const value = t.type === "checkbox" ? t.checked : t.value;
    setBind(t.dataset.bind, value);
    if (t.dataset.bind.endsWith(".speaks")) {
      const box = t.closest(".row").querySelector(".timbre");
      if (box) box.hidden = !t.checked;
    }
    if (t.dataset.bind.endsWith(".voiceId")) {
      const phrase = t.closest(".timbre").querySelector(".voice-phrase");
      if (phrase) phrase.textContent = voicePhrase(t.value);
    }
    touch();
  }
  if (t.dataset.appear) {
    S.project.appearance[t.dataset.appear] = t.value;
    applyAppearance(S.project.appearance);
    touch();
  }
  if (t.dataset.provider) {
    S.project.ai[t.dataset.provider][t.dataset.key] = t.value;
    touch();
  }
});

document.addEventListener("change", async (ev) => {
  const t = ev.target;
  if (t.dataset.bind === "style" || t.dataset.bind === "mode" || t.dataset.bind === "model" || t.dataset.bind === "audioPolicy") {
    paint();
    scheduleAssemble();
  }
  if (t.dataset.camera != null) {
    const cam = (S.banks.cameras || []).find((c) => c.keyword === t.value);
    const c = clip();
    const shot = c.shots[Number(t.dataset.camera)];
    shot.cameraKey = t.value;
    if (cam) {
      shot.cameraMove = cam.phrase;
      const input = t.closest(".row").querySelector(`[data-bind="shots.${t.dataset.camera}.cameraMove"]`);
      if (input) input.value = cam.phrase;
    }
    touch();
  }
  if (t.dataset.expression != null && t.value) {
    const c = clip();
    const shot = c.shots[Number(t.dataset.expression)];
    shot.text = (shot.text ? shot.text.replace(/\.\s*$/, "") + ". " : "") + t.value.replace(/\.\s*$/, "") + ".";
    paint();
    touch();
  }
  if (t.dataset.task) {
    const c = clip();
    const set = new Set(c.taskTypes || []);
    if (t.checked) set.add(t.dataset.task);
    else set.delete(t.dataset.task);
    c.taskTypes = [...set];
    touch();
  }
  if (t.id === "offline") {
    S.project.ai.offline = t.checked;
    touch();
    paintPreview();
  }
  if (t.id === "active-provider") {
    S.project.ai.active = t.value;
    touch();
    paintSettings();
  }
  if (t.dataset.secret && t.value.trim()) {
    try {
      await api("/api/secrets", { provider: t.dataset.secret, key: t.value.trim() });
      S.keys[t.dataset.secret] = true;
      t.value = "";
      const status = document.getElementById("status-" + t.dataset.secret);
      if (status) status.textContent = "Key saved on this machine.";
    } catch (err) {
      alert(err.message);
    }
  }
});

document.addEventListener("click", async (ev) => {
  const t = ev.target.closest("button, [data-focus]");
  if (!t) return;
  if (t.dataset.mode) {
    S.mode = t.dataset.mode;
    ensureClip();
    paint();
    assembleActive();
    saveLocal();
    return;
  }
  if (t.dataset.pick) { selectClip(t.dataset.pick); saveLocal(); return; }
  if (t.dataset.focus) {
    const el = document.getElementById(t.dataset.focus);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  const id = t.id;
  if (id === "add-clip") return addClip();
  if (id === "add-subject") return addSubject();
  if (id === "add-extra") return addExtra();
  if (id === "add-anchor") return addAnchor();
  if (id === "add-video") return addVideo();
  if (id === "add-shot") return addShot();
  if (id === "rebuild-retention") return rebuildRetention();
  if (id === "copy-prompt") return copyPrompt();
  if (id === "download-prompt") return downloadPrompt();
  if (id === "ai-reformat") return runAI("reformat");
  if (id === "ai-grammar") return runAI("grammar");
  if (id === "ai-summary") return runAI("summary");
  if (id === "clear-draft") { if (clip()) clip().aiDraft = ""; paintPreview(); touch(); return; }
  if (id === "act-save") return downloadProject();
  if (id === "act-save-disk") return saveToDisk();
  if (id === "act-open") return openFile();
  if (id === "act-export") return exportScene();
  if (id === "act-import-scene") return importScene();
  if (t.dataset.browse) return browseInto(t.dataset.browse);
  if (t.dataset.addLine != null) return addLine(Number(t.dataset.addLine));
  if (t.dataset.remove) return removeThing(t.dataset.remove, t);
  if (t.dataset.move) return moveThing(t.dataset.move, Number(t.dataset.index), Number(t.dataset.dir));
  if (t.dataset.useAi) {
    S.project.ai.active = t.dataset.useAi;
    const cfg = S.project.ai[t.dataset.useAi] || {};
    S.providerStatus = S.providerStatus || {};
    S.providerStatus[t.dataset.useAi] = "AI buttons now use this provider.";
    if (!(S.models[t.dataset.useAi] || []).length) refreshModels(t.dataset.useAi);
    else { paintSettings(); saveLocal(); }
    return;
  }
  if (t.dataset.test) return testProvider(t.dataset.test);
  if (t.dataset.models) return refreshModels(t.dataset.models);
});

function addClip() {
  const mode = S.mode === "settings" ? "ref2va" : S.mode;
  const c = blankClip(mode);
  const n = S.project.clips.filter((x) => x.mode === mode).length + 1;
  c.title = `Clip ${n}`;
  S.project.clips.push(c);
  S.clipId = c.id;
  S.mode = mode;
  paint();
  touch();
}

function blankClip(mode) {
  const base = structuredClone(S.template);
  base.id = uid("c");
  base.mode = mode;
  base.ratio = mode === "t2va" ? "16:9" : "adaptive";
  base.subjects = [];
  base.extras = [];
  base.videos = [];
  base.anchors = [];
  base.retention = [];
  base.shots = [newShot(1, base.durationSec)];
  base.taskTypes = mode === "ref2va" ? ["reference generation"] : [];
  if (mode === "ref2va") {
    const s = newSubject(base);
    s.name = "the woman";
    base.subjects = [s];
  } else {
    const s = newSubject(base);
    s.name = "the woman";
    base.subjects = [s];
  }
  base.frames = { first: "", last: "" };
  base.headers = { handoffFrom: "", endFrame: "", next: "" };
  base.styleOpening = styleOpening(base.style);
  return base;
}

function addSubject() {
  const c = clip();
  const s = newSubject(c);
  c.subjects.push(s);
  paint(); touch();
}
function addExtra() {
  const c = clip();
  c.extras.push({ label: nextFree(c), file: "", description: "", marker: "attribute_transfer" });
  paint(); touch();
}
function addAnchor() {
  const c = clip();
  const pics = pictureChoices(c);
  c.anchors.push({ imageLabel: Number(pics[0] || 1), shot: 1, kind: "composition", note: "defining the framing and layout" });
  paint(); touch();
}
function addVideo() {
  const c = clip();
  c.videos.push({ label: (c.videos.length || 0) + 1, file: "", role: "camera path", description: "" });
  paint(); touch();
}
function addShot() {
  const c = clip();
  c.shots.push(newShot(c.shots.length + 1, Number(c.durationSec) || 8));
  reflow(c);
  paint(); touch();
}
function addLine(si) {
  const c = clip();
  const who = (c.subjects[0] && c.subjects[0].id) || "";
  c.shots[si].lines.push({ subjectId: who, language: "English", native: "", delivery: "", closeMouth: true, continuation: "" });
  const sub = c.subjects.find((s) => s.id === who);
  if (sub) sub.speaks = true;
  paint(); touch();
}

function removeThing(kind, t) {
  const c = clip();
  const i = Number(t.dataset.index);
  if (kind === "subject") c.subjects.splice(i, 1);
  if (kind === "extra") c.extras.splice(i, 1);
  if (kind === "anchor") c.anchors.splice(i, 1);
  if (kind === "video") c.videos.splice(i, 1);
  if (kind === "retention") c.retention.splice(i, 1);
  if (kind === "shot") {
    c.shots.splice(i, 1);
    if (!c.shots.length) c.shots.push(newShot(1, c.durationSec));
    reflow(c);
  }
  if (kind === "line") c.shots[Number(t.dataset.shot)].lines.splice(i, 1);
  paint(); touch();
}

function moveThing(kind, index, dir) {
  const c = clip();
  const arr = kind === "shot" ? c.shots : c.subjects;
  const j = index + dir;
  if (j < 0 || j >= arr.length) return;
  const [item] = arr.splice(index, 1);
  arr.splice(j, 0, item);
  if (kind === "shot") reflow(c);
  paint(); touch();
}

async function rebuildRetention() {
  const c = clip();
  normalizeShotsText(c);
  const data = await api("/api/retention", { clip: c });
  c.retention = data.retention || [];
  paint(); touch();
}

function normalizeShotsText(c) {
  (c.retention || []).forEach((r) => {
    if (typeof r.shotsText === "string") {
      r.shots = r.shotsText.split(/[, ]+/).map(Number).filter(Boolean);
      delete r.shotsText;
    }
  });
}

function copyPrompt() {
  const text = S.prompt || "";
  navigator.clipboard.writeText(text).then(
    () => { $("#copy-prompt").textContent = "Copied"; setTimeout(() => { const b = $("#copy-prompt"); if (b) b.textContent = "Copy"; }, 1200); },
    () => alert(text),
  );
}

function downloadPrompt() {
  const c = clip();
  if (!c) return;
  const name = `clip-01-${c.durationSec}s.txt`;
  const blob = new Blob([withHeaders(c, S.prompt)], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

function withHeaders(c, body) {
  const h = c.headers || {};
  const lines = [];
  if (h.handoffFrom) lines.push(`handoff-from: ${h.handoffFrom}`);
  if (h.endFrame) lines.push(`end-frame: ${h.endFrame}`);
  if (h.next) lines.push(`next: ${h.next}`);
  const text = (body || "").trim() + "\n";
  return lines.length ? lines.join("\n") + "\n\n" + text : text;
}

function downloadProject() {
  normalizeAll();
  const blob = new Blob([JSON.stringify(S.project, null, 2) + "\n"], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (S.project.title || "project").replace(/\s+/g, "-").toLowerCase() + ".h3m.json";
  a.click();
  URL.revokeObjectURL(a.href);
}

function normalizeAll() {
  S.project.clips.forEach(normalizeShotsText);
}

async function saveToDisk() {
  const path = await ask("Save project to", S.project.savePath || (S.project.title || "project") + ".h3m.json");
  if (!path) return;
  normalizeAll();
  S.project.savePath = path;
  const data = await api("/api/save", { path, project: S.project });
  alert("Saved " + data.path);
}

function openFile() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json,.txt,application/json,text/plain";
  input.onchange = async () => {
    const file = input.files && input.files[0];
    if (!file) return;
    const text = await file.text();
    if (file.name.endsWith(".txt")) {
      const data = await api("/api/import/prompt", { text, mode: S.mode === "settings" ? "ref2va" : S.mode });
      S.project.clips.push(data.clip);
      S.clipId = data.clip.id;
      S.mode = data.clip.mode;
      paint();
      await assembleActive();
      return;
    }
    const project = JSON.parse(text);
    if (!project.clips) throw new Error("That file is not an h3-mechanic project.");
    adopt(project);
  };
  input.click();
}

function adopt(project) {
  S.project = project;
  S.project.appearance = Object.assign({ theme: "light", accent: "blue", fontScale: "1", scriptFont: "" }, project.appearance);
  applyAppearance(S.project.appearance);
  S.clipId = (project.clips[0] && project.clips[0].id) || null;
  S.mode = (project.clips[0] && project.clips[0].mode) || "ref2va";
  paint();
  assembleActive();
  saveLocal();
}

async function exportScene() {
  const directory = await ask("Export folder", "");
  if (!directory) return;
  normalizeAll();
  let data = await api("/api/export", { directory, clips: S.project.clips });
  if ((data.skipped || []).length) {
    const again = confirm(data.skipped.join("\n") + "\n\nThose clips still have errors. Export them too?");
    if (again) data = await api("/api/export", { directory, clips: S.project.clips, force: true });
  }
  alert("Wrote\n" + (data.written || []).join("\n"));
}

async function importScene() {
  const directory = await ask("Scene folder", "");
  if (!directory) return;
  const data = await api("/api/import/scene", { directory });
  S.project.clips.push(...data.clips);
  S.clipId = data.clips[0].id;
  S.mode = data.clips[0].mode;
  paint();
  assembleActive();
  saveLocal();
}

function ask(title, value) {
  return new Promise((resolve) => {
    const modal = $("#modal");
    const show = (val) => {
      modal.className = "modal-bg open";
      modal.innerHTML = `<div class="modal">
        <h2>${esc(title)}</h2>
        <label>Path <input id="ask-path" value="${esc(val || "")}" /></label>
        <div class="bar">
          <button type="button" id="ask-browse">Browse</button>
          <button type="button" class="primary" id="ask-ok">Use this path</button>
          <button type="button" id="ask-cancel">Cancel</button>
        </div>
      </div>`;
      $("#ask-ok").onclick = () => { modal.className = "modal-bg"; resolve($("#ask-path").value.trim()); };
      $("#ask-cancel").onclick = () => { modal.className = "modal-bg"; resolve(""); };
      $("#ask-browse").onclick = async () => {
        const picked = await pickPath($("#ask-path").value);
        show(picked || val);
      };
    };
    show(value);
  });
}

async function browseInto(bind) {
  const picked = await pickPath("");
  if (!picked) return;
  setBind(bind, picked);
  paint();
  touch();
}

function pickPath(start) {
  const modal = $("#modal");
  return new Promise((resolve) => {
    async function load(path) {
      let data;
      try {
        data = await api("/api/browse?path=" + encodeURIComponent(path || ""));
      } catch (err) {
        modal.className = "modal-bg";
        alert(err.message);
        resolve("");
        return;
      }
      modal.className = "modal-bg open";
      modal.innerHTML = `<div class="modal">
        <h2>Choose a file or folder</h2>
        <p class="hint">${esc(data.path)}</p>
        <div class="finder" id="finder"></div>
        <div class="bar">
          <button type="button" id="use-folder">Use this folder</button>
          <button type="button" id="browse-cancel">Cancel</button>
        </div>
      </div>`;
      const finder = $("#finder");
      finder.innerHTML = `<button type="button" data-dir="${esc(data.parent)}">..</button>`
        + data.dirs.map((d) => `<button type="button" data-dir="${esc(data.path + "/" + d)}">${esc(d)}/</button>`).join("")
        + data.files.map((f) => `<button type="button" data-file="${esc(data.path + "/" + f)}">${esc(f)}</button>`).join("");
      finder.onclick = (ev) => {
        const b = ev.target.closest("button");
        if (!b) return;
        if (b.dataset.dir) load(b.dataset.dir);
        if (b.dataset.file) { modal.className = "modal-bg"; resolve(b.dataset.file); }
      };
      $("#use-folder").onclick = () => { modal.className = "modal-bg"; resolve(data.path); };
      $("#browse-cancel").onclick = () => { modal.className = "modal-bg"; resolve(""); };
    }
    load(start || "");
  });
}

async function runAI(action) {
  const c = clip();
  if (!c) return;
  if (S.project.ai.offline) return;
  const id = S.project.ai.active;
  const cfg = S.project.ai[id] || {};
  const btn = document.getElementById(action === "summary" ? "ai-summary" : action === "grammar" ? "ai-grammar" : "ai-reformat");
  if (btn) btn.disabled = true;
  try {
    const data = await api("/api/ai", {
      action, provider: id, baseUrl: cfg.baseUrl, model: cfg.model,
      offline: false, clip: c, draft: S.prompt,
    });
    if (action === "summary") c.summary = data.text;
    else c.aiDraft = data.text;
    paint();
    touch();
  } catch (err) {
    alert(err.message);
  } finally {
    if (btn) btn.disabled = !!S.project.ai.offline;
  }
}

function acceptModels(id, data, note) {
  const cfg = S.project.ai[id] || (S.project.ai[id] = { baseUrl: "", model: "" });
  if (data.baseUrl) cfg.baseUrl = data.baseUrl;
  const found = data.models || [];
  if (found.length) {
    S.models[id] = found;
    if (!cfg.model) cfg.model = found[0];
  }
  S.providerStatus = S.providerStatus || {};
  S.providerStatus[id] = note || (found.length ? `${found.length} models` : "Connected. Type a model name, or refresh the list.");
  rememberModels();
  if (S.mode === "settings") paintSettings();
  saveLocal();
}

async function testProvider(id) {
  const cfg = S.project.ai[id];
  S.providerStatus = S.providerStatus || {};
  S.providerStatus[id] = "Testing…";
  if (S.mode === "settings") paintSettings();
  try {
    const data = await api("/api/provider/test", { provider: id, baseUrl: cfg.baseUrl, model: cfg.model });
    if (!(data.models || []).length) {
      try {
        const listed = await api("/api/provider/models", { provider: id, baseUrl: data.baseUrl || cfg.baseUrl, detect: id === "ollama" });
        data.models = listed.models || [];
        data.baseUrl = listed.baseUrl || data.baseUrl;
      } catch { /* the connection itself succeeded */ }
    }
    acceptModels(id, data, data.detail || "Connected.");
  } catch (err) {
    S.providerStatus[id] = err.message;
    if (S.mode === "settings") paintSettings();
  }
}

async function refreshModels(id) {
  const cfg = S.project.ai[id];
  S.providerStatus = S.providerStatus || {};
  S.providerStatus[id] = "Looking…";
  if (S.mode === "settings") paintSettings();
  try {
    const data = await api("/api/provider/models", { provider: id, baseUrl: cfg.baseUrl, detect: id === "ollama" });
    acceptModels(id, data, `${(data.models || []).length} models`);
  } catch (err) {
    S.providerStatus[id] = err.message;
    if (S.mode === "settings") paintSettings();
  }
}

/* drag */
let drag = null;
document.addEventListener("dragstart", (ev) => {
  const row = ev.target.closest("[data-drop]");
  if (!row) return;
  drag = { kind: row.dataset.drop, id: row.dataset.id, index: Number(row.dataset.index) };
  row.classList.add("drag");
});
document.addEventListener("dragend", () => {
  document.querySelectorAll(".drag").forEach((el) => el.classList.remove("drag"));
  drag = null;
});
document.addEventListener("dragover", (ev) => {
  if (ev.target.closest("[data-drop]")) ev.preventDefault();
});
document.addEventListener("drop", (ev) => {
  const row = ev.target.closest("[data-drop]");
  if (!row || !drag || row.dataset.drop !== drag.kind) return;
  ev.preventDefault();
  if (drag.kind === "clip") {
    const from = S.project.clips.findIndex((c) => c.id === drag.id);
    const to = S.project.clips.findIndex((c) => c.id === row.dataset.id);
    if (from < 0 || to < 0 || from === to) return;
    const [item] = S.project.clips.splice(from, 1);
    S.project.clips.splice(to, 0, item);
  } else if (drag.kind === "shot" || drag.kind === "subject") {
    const arr = drag.kind === "shot" ? clip().shots : clip().subjects;
    const from = drag.index;
    const to = Number(row.dataset.index);
    if (from === to) return;
    const [item] = arr.splice(from, 1);
    arr.splice(to, 0, item);
    if (drag.kind === "shot") reflow(clip());
  }
  paint();
  touch();
});

async function boot() {
  const data = await api("/api/banks");
  S.banks = data.banks;
  S.template = data.project.clips[0];
  let stored = null;
  try { stored = JSON.parse(localStorage.getItem("h3m:project") || "null"); } catch { stored = null; }
  S.project = stored && stored.clips ? stored : data.project;
  S.project.appearance = Object.assign({ theme: "light", accent: "blue", fontScale: "1", scriptFont: "" }, S.project.appearance);
  S.project.ai = Object.assign(data.project.ai, S.project.ai || {});
  const savedLook = localStorage.getItem("h3m:appearance");
  if (savedLook) {
    try { Object.assign(S.project.appearance, JSON.parse(savedLook)); } catch { /* keep project */ }
  }
  applyAppearance(S.project.appearance);
  S.mode = localStorage.getItem("h3m:mode") || (S.project.clips[0] && S.project.clips[0].mode) || "ref2va";
  S.clipId = localStorage.getItem("h3m:clip") || (S.project.clips[0] && S.project.clips[0].id);
  try { S.keys = (await api("/api/secrets")).keys || {}; } catch { S.keys = {}; }
  paint();
  assembleActive();
}

boot().catch((err) => {
  document.body.insertAdjacentHTML("beforeend", `<p class="card">${esc(err.message)}</p>`);
});
