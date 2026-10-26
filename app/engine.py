"""Pure MiniMax H3 prompt engine: clip defaults, render, checks, import.

Identical clips render to identical text. No network, no UI.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import studio

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "rules" / "rules.json"

CLOSING = (
    "The audio contains only the spoken dialogue, with no background music, "
    "no ambience, and no sound effects."
)

STYLES = {
    "80s-bollywood": (
        "The target video is in a 1980s Hindi masala-film style with saturated "
        "Eastmancolor color, 35mm film grain, and a soft diffusion glow."
    ),
    "cinematic-modern": (
        "The target video is in a modern cinematic feature-film style with "
        "motivated low-key lighting, shallow depth of field, and an anamorphic widescreen frame."
    ),
    "modern-series": (
        "The target video is in a modern streaming-series style with naturalistic "
        "soft light, a muted desaturated grade, and subtly handheld coverage."
    ),
    "noir-thriller": (
        "The target video is in a neo-noir crime-thriller style with hard low-key "
        "light, venetian-blind shadows, and sodium-and-neon night color."
    ),
    "generic": "",
}

SIZES = {
    "close-up": "a close-up",
    "medium close-up": "a medium close-up",
    "medium": "a medium shot",
    "medium-wide": "a medium-wide shot",
    "wide": "a wide shot",
    "extreme wide": "an extreme wide shot",
    "establishing": "an establishing shot",
}
ANGLES = {
    "front": "front-facing",
    "three-quarter": "in a three-quarter view",
    "side": "in side profile",
    "behind": "from behind",
    "low": "in a low angle",
    "high": "in a high angle",
    "overhead": "in an overhead shot",
}
CONCRETE_RATIOS = ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"]
TASK_TYPES = [
    "reference generation",
    "keyframe completion",
    "video editing",
    "video continuation",
    "audio reuse",
    "audio reference",
]
VISUAL_MARKERS = ["fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference"]
AUDIO_MARKERS = ["fully_copy", "partially_copy", "reference", "weak_reference"]
LANGUAGES = ["English", "Kannada", "Hindi", "Tamil", "Telugu", "Malayalam", "Marathi", "Bengali"]
MOVE_VERBS = (
    "zoom", "push", "pull", "track", "truck", "pan", "tilt", "pedestal",
    "crane", "boom", "arc", "orbit", "roll", "static", "hold", "shake",
    "rack", "dolly", "pov", "handheld", "locked",
)
STATIC_VERBS = ("static", "locked", "hold", "pov", "shake", "handheld")
LANDING = ("toward", "revealing", " as ", "onto", "keeping", "while", "alongside", "from ")
WIDE_SIZES = {"wide", "extreme wide", "establishing", "medium-wide"}
FACE_ANGLES = {"front", "three-quarter"}

# Library phrases used when rules.json has no Voice Library sheet.
FALLBACK_VOICES = {
    "F1": "in a soft, breathy young female voice with a slow, gentle pace",
    "F2": "in a bright, clear young female voice with a lively, brisk pace",
    "F3": "in a warm, velvety female voice in her thirties with a calm, even pace",
    "F4": "in a low, husky female voice with a slightly smoky texture and an unhurried pace",
    "F5": "in a crisp, authoritative mid-low female voice with precise diction and a measured pace",
    "M1": "in a deep, gravelly middle-aged male voice with a slow, measured pace",
    "M5": "in a hard, clipped mid-low male voice with a brisk staccato pace",
    "K1": "in a small, high, clear little girl's voice",
    "K2": "in a small, bright little boy's voice with an excited pace",
}


def load_rules() -> dict:
    if not RULES_PATH.is_file():
        return {"sheets": {}}
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def _rows(rules: dict, sheet: str) -> list:
    return list((rules.get("sheets") or {}).get(sheet) or [])


def camera_phrase(snippet: str) -> str:
    text = re.sub(r"^The camera\s+", "", (snippet or "").strip(), flags=re.I)
    return text.rstrip(".").strip()


def _is_move_row(row: dict) -> bool:
    blob = f"{row.get('keyword', '')} {row.get('snippet', '')}".lower()
    return "camera" in blob and any(v in blob for v in MOVE_VERBS)


def banks(rules: dict | None = None) -> dict:
    rules = rules if rules is not None else load_rules()
    cameras = []
    for row in _rows(rules, "Camera Moves"):
        if not _is_move_row(row):
            continue
        cameras.append({
            "keyword": row.get("keyword") or "",
            "phrase": camera_phrase(row.get("snippet") or ""),
            "snippet": row.get("snippet") or "",
            "example": row.get("example") or "",
        })
    voices = []
    for row in _rows(rules, "Voice Library"):
        key = (row.get("keyword") or "").strip()
        ident = key.split()[0] if key else ""
        if not ident:
            continue
        voices.append({
            "id": ident,
            "keyword": key,
            "phrase": (row.get("snippet") or "").strip(),
            "example": row.get("example") or "",
        })
    if not voices:
        voices = [{"id": k, "keyword": k, "phrase": v, "example": ""} for k, v in FALLBACK_VOICES.items()]
    expressions = []
    for row in _rows(rules, "Faces & Performance"):
        cat = row.get("category") or ""
        if cat.startswith("Facial") or cat.startswith("Emotion"):
            expressions.append({
                "keyword": row.get("keyword") or "",
                "snippet": row.get("snippet") or "",
                "example": row.get("example") or "",
            })
    for extra in studio.extra_styles():
        if extra.get("id") and extra.get("id") not in STYLES:
            STYLES[extra["id"]] = extra.get("opening") or ""
    payload = {
        "styles": [{"id": k, "opening": v} for k, v in STYLES.items()],
        "sizes": list(SIZES),
        "angles": list(ANGLES),
        "lenses": ["24mm", "35mm", "50mm", "85mm", ""],
        "ratios": CONCRETE_RATIOS,
        "taskTypes": TASK_TYPES,
        "visualMarkers": VISUAL_MARKERS,
        "audioMarkers": AUDIO_MARKERS,
        "languages": LANGUAGES,
        "cameras": cameras,
        "voices": voices,
        "expressions": expressions[:40],
    }
    payload.update(studio.catalog())
    return payload


def _id(prefix: str) -> str:
    import random
    return prefix + f"{random.randrange(16**8):08x}"


def new_shot(index: int, duration: int) -> dict:
    start = None if index == 1 else min(duration - 1, 3 * (index - 1))
    return {
        "size": "medium close-up",
        "angle": "front",
        "lens": "85mm",
        "cameraMove": "holds a static shot",
        "cameraKey": "Static / Static Shot / Locked-off establishing",
        "startSec": start,
        "text": "",
        "custom": False,
        "offscreenGuard": False,
        "lines": [],
    }


def new_subject() -> dict:
    return {
        "id": _id("s"),
        "name": "",
        "kind": "person",
        "gender": "female",
        "speaks": False,
        "imageLabel": 1,
        "imageFile": "",
        "description": "",
        "timbre": "library",
        "voiceId": "F3",
        "customVoice": "",
        "audioLabel": 1,
        "audioFile": "",
    }


def new_clip(mode: str = "ref2va") -> dict:
    mode = mode if mode in ("t2va", "i2va", "fl2va", "l2va", "ref2va") else "ref2va"
    ratio = "16:9" if mode == "t2va" else "adaptive"
    clip = {
        "id": _id("c"),
        "mode": mode,
        "title": "Clip 1",
        "model": "H3",
        "durationSec": 8,
        "resolution": "768P",
        "ratio": ratio,
        "audioPolicy": "dialogue-only",
        "style": "cinematic-modern",
        "styleOpening": STYLES["cinematic-modern"],
        "soundscape": "",
        "music": "",
        "notes": "",
        "taskTypes": ["reference generation"] if mode == "ref2va" else [],
        "summary": "",
        "headers": {"handoffFrom": "", "endFrame": "", "next": ""},
        "subjects": [],
        "extras": [],
        "videos": [],
        "anchors": [],
        "retention": [],
        "frames": {"first": "", "last": ""},
        "shots": [new_shot(1, 8)],
    }
    if mode == "ref2va":
        sub = new_subject()
        sub["name"] = "the woman"
        sub["imageLabel"] = 1
        clip["subjects"] = [sub]
        clip["retention"] = sync_retention(clip)
    else:
        sub = new_subject()
        sub["name"] = "the woman"
        sub["speaks"] = False
        clip["subjects"] = [sub]
    return studio.prepare_clip(clip)


def new_project() -> dict:
    project = {
        "schemaVersion": 2,
        "houseAudio": "dialogue-only",
        "screenDirection": "ltr",
        "library": {"cast": [], "locations": []},
        "scenes": [],
        "title": "Untitled project",
        "appearance": {"theme": "light", "accent": "blue", "fontScale": "1", "scriptFont": ""},
        "ai": {
            "offline": False,
            "active": "ollama",
            "deepseek": {"baseUrl": "https://api.deepseek.com", "model": "deepseek-chat"},
            "claude": {"baseUrl": "https://api.anthropic.com", "model": "claude-sonnet-4-5"},
            "gemini": {"baseUrl": "https://generativelanguage.googleapis.com/v1beta", "model": "gemini-2.5-flash"},
            "openai": {"baseUrl": "http://127.0.0.1:8080/v1", "model": ""},
            "ollama": {"baseUrl": "http://127.0.0.1:11434", "model": ""},
        },
        "clips": [new_clip("ref2va")],
    }
    return studio.prepare_project(project)


def _subjects(clip: dict) -> list:
    return list(clip.get("subjects") or [])


def subject_number(clip: dict, sid: str) -> int | None:
    for i, s in enumerate(_subjects(clip), start=1):
        if s.get("id") == sid:
            return i
    return None


def speaker_map(clip: dict) -> dict:
    order = []
    for shot in clip.get("shots") or []:
        for line in shot.get("lines") or []:
            sid = line.get("subjectId")
            if sid and sid not in order:
                order.append(sid)
    return {sid: f"S{i}" for i, sid in enumerate(order, start=1)}


def voice_phrase(subject: dict, voice_index: dict) -> str:
    kind = subject.get("timbre") or "library"
    if kind == "audio" and subject.get("audioFile"):
        return f"in the voice of <Audio {subject.get('audioLabel') or 1}>"
    if kind == "custom" and (subject.get("customVoice") or "").strip():
        text = subject["customVoice"].strip()
        return text if text.lower().startswith("in ") else "in " + text
    ident = subject.get("voiceId") or "F3"
    return voice_index.get(ident) or FALLBACK_VOICES.get(ident) or f"in the {ident} library voice"


def _pronoun(gender: str) -> tuple[str, str]:
    if gender == "male":
        return "He", "his"
    if gender == "female":
        return "She", "her"
    return "They", "their"


def _subject_definition(clip: dict, subject: dict, number: int) -> str:
    desc = (subject.get("description") or "").strip()
    pic = subject.get("imageLabel") or number
    if not desc:
        kind = subject.get("kind") or "person"
        name = re.sub(r"^the\s+", "", (subject.get("name") or kind).strip(), flags=re.I)
        if kind == "person":
            _, poss = _pronoun(subject.get("gender"))
            desc = (
                f"the {name} in <Picture {pic}>, with {poss} face, hair, build, "
                "and complete outfit taken exactly from the reference"
            )
        else:
            desc = f"the {name} in <Picture {pic}>, exactly as shown"
    desc = desc.rstrip(".")
    if desc[:1].isupper():
        desc = desc[:1].lower() + desc[1:]
    if not desc.lower().startswith("the "):
        desc = "the " + desc
    line = f"<Subject {number}> is {desc}."
    if subject.get("identityOnly"):
        line += (
            f" <Picture {pic}> supplies identity only, and the framing of every shot "
            "comes from the description below, not from the reference image."
        )
    return line


def _audio_definition(subject: dict, number: int, speaker: str | None) -> str:
    who = f"<Subject {number}>"
    suffix = f" ({speaker})" if speaker else ""
    return f"<Audio {subject.get('audioLabel') or 1}> is the voice-timbre reference for {who}{suffix}."


def format_time(sec) -> str:
    sec = float(sec or 0)
    if sec < 0:
        sec = 0
    minutes = int(sec // 60)
    rest = sec - minutes * 60
    whole = int(rest)
    ms = int(round((rest - whole) * 1000))
    if ms == 1000:
        whole += 1
        ms = 0
    if whole == 60:
        minutes += 1
        whole = 0
    return f"{minutes:02d}:{whole:02d}.{ms:03d}"


def _opening_bits(shot: dict) -> str:
    parts = []
    size = SIZES.get(shot.get("size") or "", shot.get("size") or "")
    angle = ANGLES.get(shot.get("angle") or "", "")
    if size:
        parts.append(size)
    if angle:
        parts.append(angle)
    lens = (shot.get("lens") or "").strip()
    if lens:
        parts.append(f"shot on an {lens} lens" if lens[0].isdigit() and lens[0] == "8" else f"shot on a {lens} lens")
    return ", ".join(parts)


def _anchor_prefix(clip: dict, shot_index: int) -> str:
    bits = []
    for a in clip.get("anchors") or []:
        if int(a.get("shot") or 0) != shot_index:
            continue
        pic = a.get("imageLabel")
        kind = a.get("kind") or "composition"
        if kind == "keyframe":
            bits.append(f"the shot's keyframe corresponds to <Picture {pic}>")
        elif kind == "end":
            bits.append(f"the shot ends on <Picture {pic}>")
        else:
            bits.append(f"The shot begins from <Picture {pic}>")
    if not bits:
        return ""
    return ". ".join(bits) + ". "


def _dialogue(clip: dict, shot: dict, speakers: dict, voice_index: dict) -> list[str]:
    out = []
    mode = clip.get("mode")
    by_id = {s.get("id"): s for s in _subjects(clip)}
    for line in shot.get("lines") or []:
        sub = by_id.get(line.get("subjectId"))
        if sub is None and _subjects(clip):
            sub = _subjects(clip)[0]
        if sub is None:
            handle = "The speaker"
            gender = ""
            voice = "in a clear voice"
            speaker = "S1"
        else:
            number = subject_number(clip, sub.get("id"))
            speaker = speakers.get(sub.get("id"), "S1")
            if mode == "ref2va":
                handle = f"<Subject {number}>"
            else:
                handle = (sub.get("name") or "The speaker").strip()
                if handle:
                    handle = handle[0].upper() + handle[1:]
            gender = sub.get("gender")
            voice = voice_phrase(sub, voice_index)
            accent = (sub.get("accent") or "").strip()
            if accent:
                voice = f"{voice}, {accent}"
        delivery = (line.get("delivery") or "").strip()
        if line.get("voiceover"):
            say = f"{handle} ({speaker}) says in an off-screen voiceover, {voice}"
        else:
            say = f"{handle} ({speaker}) says {voice}"
        if delivery:
            say += ", " + delivery.rstrip(",")
        lang = line.get("language") or "English"
        native = line.get("native") or ""
        say += f", <d>[{lang}] {native}</d>"
        cont = line.get("continuation")
        if cont == "scenetrans":
            say += "<scenetrans> The audio continues across the cut."
        elif cont == "cutoff":
            say += "<cutoff>"
        if line.get("voiceover"):
            person, poss = _pronoun(gender)
            if person == "They":
                say += " Their lips remain completely closed."
            else:
                say += f" {person}'s lips remain completely closed."
            del poss
        elif line.get("closeMouth", True):
            person, _ = _pronoun(gender)
            if person == "They":
                say += " The lips close."
            else:
                say += f" {person} closes {('her' if gender == 'female' else 'his')} lips."
        out.append(say)
    return out


def _shot_sentence(clip: dict, shot: dict, index: int, first: bool, speakers, voice_index) -> str:
    mode = clip.get("mode")
    head = f"[Shot {index}] "
    if not first:
        verb = "the shot cuts to" if mode == "ref2va" else "the camera cuts to"
        head += f"At {format_time(shot.get('startSec'))}, {verb} "
    if first and mode == "ref2va":
        head += _anchor_prefix(clip, index)
    elif first and mode in ("i2va", "fl2va"):
        head += "Live-action, cinematic, the subject shown in <Picture 1>, "
    elif first and mode == "t2va":
        head += "Live-action, cinematic, "

    if shot.get("custom") and (shot.get("text") or "").strip():
        body = shot["text"].strip().rstrip(".") + "."
    else:
        bits = _opening_bits(shot)
        action = (shot.get("text") or "").strip().rstrip(".")
        body = ""
        if bits:
            # Capitalize only when the shot tag is not already mid-sentence.
            if head.rstrip().endswith(","):
                body += bits + "."
            else:
                body += bits[0].upper() + bits[1:] + "."
        if action:
            body += (" " if body else "") + action + "."
        if not body:
            body = "The frame holds."
    if mode == "ref2va" and not first:
        anchor = _anchor_prefix(clip, index)
        if anchor:
            body = anchor + body
    move = (shot.get("cameraMove") or "").strip().rstrip(".")
    if move:
        body += " The camera " + move + "."
    for line in _dialogue(clip, shot, speakers, voice_index):
        body += " " + line
    if shot.get("expression") and shot["expression"] not in body:
        body += " " + shot["expression"].strip().rstrip(".") + "."
    if shot.get("eyeline"):
        body += " " + shot["eyeline"].strip().rstrip(".") + "."
    if shot.get("onScreenText"):
        if shot.get("onScreenReadable", True):
            body += f' A sign reads "{shot["onScreenText"].strip()}".'
        else:
            body += " A sign is visible, its lettering not readable."
    if shot.get("diegetic"):
        body += " " + shot["diegetic"].strip().rstrip(".") + "."
    if shot.get("offscreenGuard") and "No other person appears" not in body:
        body += " No other person appears in the frame."
    return head + body


def _style_text(clip: dict) -> str:
    opening = (clip.get("styleOpening") or "").strip()
    if clip.get("audioPolicy") != "dialogue-only":
        text = opening.rstrip(".") + "." if opening else ""
    else:
        base = opening.rstrip(".")
        if CLOSING in opening:
            text = opening if opening.endswith(".") else opening + "."
        elif base:
            text = base + ". " + CLOSING
        else:
            text = CLOSING
    if text and clip.get("clipKind") == "sampler" and "exactly one view" not in text:
        text += " Each shot holds exactly one view of the subject and no other person."
    return text


def _sound(clip: dict) -> tuple[str, str]:
    if clip.get("audioPolicy") == "dialogue-only":
        return "N/A", "N/A"
    sound = (clip.get("soundscape") or "").strip()
    if not sound:
        bits = []
        for key in ("ambience", "foley", "humanSounds"):
            part = (clip.get(key) or "").strip()
            if part:
                bits.append(part.rstrip(".") + ".")
        sound = " ".join(bits)
    return sound, (clip.get("music") or "").strip()


def render_ref2va(clip: dict, voice_index: dict) -> str:
    speakers = speaker_map(clip)
    lines = []
    for i, sub in enumerate(_subjects(clip), start=1):
        lines.append(_subject_definition(clip, sub, i))
    for extra in clip.get("extras") or []:
        desc = (extra.get("description") or "a hidden attribute").strip().rstrip(".")
        lines.append(f"<Picture {extra.get('label')}> is {desc}.")
    for a in clip.get("anchors") or []:
        pic = a.get("imageLabel")
        shot = a.get("shot") or 1
        note = (a.get("note") or "defining the framing and layout").strip().rstrip(".")
        kind = a.get("kind") or "composition"
        if kind == "keyframe":
            lines.append(f"<Picture {pic}> is the keyframe anchor for [Shot {shot}], {note}.")
        elif kind == "end":
            lines.append(f"<Picture {pic}> is the end frame for [Shot {shot}], {note}.")
        else:
            lines.append(f"<Picture {pic}> is the composition anchor for [Shot {shot}], {note}.")
    for v in clip.get("videos") or []:
        desc = (v.get("description") or "a motion reference").strip().rstrip(".")
        lines.append(f"<Video {v.get('label')}> is {desc}.")
    for i, sub in enumerate(_subjects(clip), start=1):
        if sub.get("speaks") and sub.get("timbre") == "audio" and sub.get("audioFile"):
            lines.append(_audio_definition(sub, i, speakers.get(sub.get("id"))))
    subjects_block = "\n".join(lines)

    tasks = studio.effective_tasks(clip)
    summary = (clip.get("summary") or "").strip()
    prefix = " + ".join(dict.fromkeys(tasks))
    summary_block = f"[{prefix}] {summary}".strip() if prefix else summary
    if "video editing" in tasks:
        video = next((v for v in (clip.get("videos") or []) if (v.get("intent") or "") == "edit"), None)
        label = (video or {}).get("label") or 1
        lead = f"The target video is an edited version of <Video {label}>."
        if lead not in summary_block:
            summary_block = f"{lead} {summary_block}".strip()

    retention_lines = []
    for row in clip.get("retention") or []:
        label = (row.get("label") or "").strip()
        if not label:
            continue
        marker = row.get("marker") or "fully_preserved"
        note = (row.get("note") or "").strip()
        context = (row.get("context") or "").strip()
        shots = row.get("shots") or []
        if label.startswith("<Audio"):
            head = label
        elif context:
            head = f"{label} ({context})"
        elif shots:
            head = f"{label} (appears in {', '.join(f'[Shot {n}]' for n in shots)})"
        else:
            head = label
        retention_lines.append(f"{head}: {marker}" + (f" - {note}" if note else ""))
    retention_block = "\n".join(retention_lines)

    style = _style_text(clip)
    shot_lines = []
    if style:
        shot_lines.append(style)
    for i, shot in enumerate(clip.get("shots") or [], start=1):
        shot_lines.append(_shot_sentence(clip, shot, i, i == 1, speakers, voice_index))
    detail = "\n".join(shot_lines)
    sound, music = _sound(clip)
    sections = [
        ("subject_definitions", subjects_block),
        ("summary", summary_block),
        ("retention_analysis", retention_block),
        ("detailed_description", detail),
        ("overall_soundscape", sound),
        ("non_diegetic_music", music),
    ]
    return "\n\n".join(f"{name}:\n{body}" for name, body in sections) + "\n"


def _instruction(clip: dict) -> str:
    mode = clip.get("mode")
    duration = float(clip.get("durationSec") or 0)
    shots = clip.get("shots") or []
    last = len(shots) or 1
    if mode == "i2va":
        return "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."
    if mode == "fl2va":
        return (
            "How the reference pictures align with the target video — "
            f"Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
            f"Picture 2 (from Shot {last}) aligns with the {duration:.2f}-second mark of the target video."
        )
    if mode == "l2va":
        return (
            "How the reference pictures align with the target video — "
            f"<Picture 1> (from [Shot {last}]) aligns with the {duration:.2f}-second mark of the target video."
        )
    return ""


def render_base(clip: dict, voice_index: dict) -> str:
    speakers = speaker_map(clip)
    chunks = []
    dialogue_only = clip.get("audioPolicy") == "dialogue-only"
    for i, shot in enumerate(clip.get("shots") or [], start=1):
        sentence = _shot_sentence(clip, shot, i, i == 1, speakers, voice_index)
        if i == 1 and dialogue_only and CLOSING not in sentence:
            sentence = sentence.rstrip() + " " + CLOSING
        chunks.append(sentence)
    body = " ".join(chunks)
    sound, music = _sound(clip)
    parts = []
    line = _instruction(clip)
    if line:
        parts.append(line)
    parts.append(f"integrated_multimodal_description: {body}")
    parts.append(f"overall_soundscape: {sound}")
    parts.append(f"non_diegetic_music: {music}")
    return "\n\n".join(parts) + "\n"


def voice_index_from(bank: dict | None) -> dict:
    out = dict(FALLBACK_VOICES)
    for v in (bank or {}).get("voices") or []:
        if v.get("id") and v.get("phrase"):
            out[v["id"]] = v["phrase"]
    return out


def render_clip(clip: dict, bank: dict | None = None) -> str:
    index = voice_index_from(bank)
    if clip.get("mode") == "ref2va":
        return render_ref2va(clip, index)
    return render_base(clip, index)


def sync_retention(clip: dict) -> list:
    """Rebuild retention rows, keeping notes and markers already chosen."""
    old = {(r.get("label"), r.get("context") or ""): r for r in clip.get("retention") or []}
    rows = []
    shot_ns = list(range(1, len(clip.get("shots") or []) + 1)) or [1]

    def keep(label, marker, shots=None, context=""):
        prev = old.get((label, context)) or old.get((label, ""))
        rows.append({
            "label": label,
            "marker": (prev or {}).get("marker") or marker,
            "shots": (prev or {}).get("shots") if prev and prev.get("shots") else (shots or []),
            "context": context,
            "note": (prev or {}).get("note") or "",
        })

    for i, _sub in enumerate(_subjects(clip), start=1):
        keep(f"<Subject {i}>", "fully_preserved", shot_ns)
    for extra in clip.get("extras") or []:
        keep(f"<Picture {extra.get('label')}>", extra.get("marker") or "attribute_transfer", shot_ns)
    for a in clip.get("anchors") or []:
        kind = "keyframe" if a.get("kind") == "keyframe" else "composition anchor"
        keep(f"<Picture {a.get('imageLabel')}>", "fully_preserved", context=f"[Shot {a.get('shot') or 1}] {kind}")
    for v in clip.get("videos") or []:
        keep(f"<Video {v.get('label')}>", "weak_reference", context=(v.get("role") or "camera path"))
    for sub in _subjects(clip):
        if sub.get("speaks") and sub.get("timbre") == "audio":
            keep(f"<Audio {sub.get('audioLabel') or 1}>", "reference")
    return rows


def attach_order(clip: dict) -> list:
    rows = []
    mode = clip.get("mode")
    if mode == "i2va":
        rows.append({"kind": "Picture", "label": 1, "role": "opening frame", "file": (clip.get("frames") or {}).get("first") or ""})
    elif mode == "l2va":
        rows.append({"kind": "Picture", "label": 1, "role": "closing frame", "file": (clip.get("frames") or {}).get("last") or ""})
    elif mode == "fl2va":
        frames = clip.get("frames") or {}
        rows.append({"kind": "Picture", "label": 1, "role": "opening frame", "file": frames.get("first") or ""})
        rows.append({"kind": "Picture", "label": 2, "role": "closing frame", "file": frames.get("last") or ""})
    elif mode == "ref2va":
        seen = set()
        for i, sub in enumerate(_subjects(clip), start=1):
            lab = sub.get("imageLabel")
            if lab in seen:
                continue
            seen.add(lab)
            rows.append({
                "kind": "Picture", "label": lab, "role": f"Subject {i}",
                "file": sub.get("imageFile") or "", "name": sub.get("name") or "",
            })
        for extra in clip.get("extras") or []:
            rows.append({
                "kind": "Picture", "label": extra.get("label"), "role": "attribute",
                "file": extra.get("file") or "", "name": extra.get("description") or "",
            })
        for v in clip.get("videos") or []:
            rows.append({
                "kind": "Video", "label": v.get("label"), "role": v.get("role") or "camera path",
                "file": v.get("file") or "", "name": v.get("description") or "",
            })
        for sub in _subjects(clip):
            if sub.get("speaks") and sub.get("timbre") == "audio":
                rows.append({
                    "kind": "Audio", "label": sub.get("audioLabel") or 1, "role": "timbre",
                    "file": sub.get("audioFile") or "", "name": sub.get("name") or "",
                })
    for row in rows:
        row["missing"] = not (row.get("file") or "").strip()
    return rows


def _finding(fid, severity, message, focus) -> dict:
    return {"id": fid, "severity": severity, "message": message, "focus": focus}


def _labels_in(text: str) -> list[str]:
    return re.findall(r"<(?:Subject|Picture|Video|Audio) \d+>", text)


def validate_clip(clip: dict, text: str, bank: dict | None = None) -> list:
    del bank
    findings = []
    mode = clip.get("mode") or "t2va"
    model = clip.get("model") or "H3"
    try:
        duration = int(clip.get("durationSec"))
    except (TypeError, ValueError):
        duration = -1
    lo, hi = (5, 15) if model == "H3-Max" else (4, 15)
    if duration < lo or duration > hi:
        findings.append(_finding("L1", "error", f"Duration must be a whole number from {lo} to {hi} for {model}.", "sec-meta"))
    res = clip.get("resolution")
    ok_res = {"480P", "768P"} if model == "H3-Max" else {"768P", "2K"}
    if res not in ok_res:
        findings.append(_finding("L2", "error", f"{model} resolution must be {' / '.join(sorted(ok_res))}.", "sec-meta"))
    ratio = clip.get("ratio") or ""
    if mode == "t2va" and ratio not in CONCRETE_RATIOS:
        findings.append(_finding("L3", "error", "T2VA needs a concrete ratio: " + ", ".join(CONCRETE_RATIOS) + ".", "sec-meta"))
    if mode in ("i2va", "fl2va", "l2va") and ratio != "adaptive":
        findings.append(_finding("L3", "error", "Frame modes follow the image. Leave the ratio adaptive.", "sec-meta"))

    attach = attach_order(clip)
    images = [r for r in attach if r["kind"] == "Picture"]
    videos = [r for r in attach if r["kind"] == "Video"]
    audios = [r for r in attach if r["kind"] == "Audio"]
    if len(images) > 9 or len(videos) > 3 or len(audios) > 3 or len(attach) > 12:
        findings.append(_finding(
            "L4", "error",
            f"File budget is {len(images)} images, {len(videos)} videos, {len(audios)} audio "
            f"({len(attach)} total). The limit is 9 / 3 / 3 / 12.",
            "sec-cast",
        ))
    if len(text) > 7000:
        findings.append(_finding("L5", "error", f"Prompt is {len(text)} characters. The limit is 7000.", "preview"))

    if mode in ("i2va", "fl2va", "l2va") and (clip.get("extras") or clip.get("videos") or clip.get("anchors")):
        findings.append(_finding("L6", "error", "Frame modes cannot take extra reference images, videos, or anchors.", "sec-frames"))
    if mode == "i2va":
        for sub in _subjects(clip):
            if (sub.get("imageFile") or "").strip():
                findings.append(_finding("L6", "error", "I2VA cannot take a separate character image. Everyone who must match is already in the opening frame.", "sec-cast"))
                break
    if mode == "ref2va" and not images:
        findings.append(_finding("L6", "error", "Ref2VA needs at least one reference image.", "sec-cast"))

    if mode == "ref2va":
        required = ["subject_definitions:", "summary:", "retention_analysis:", "detailed_description:", "overall_soundscape:", "non_diegetic_music:"]
    else:
        required = ["integrated_multimodal_description:", "overall_soundscape:", "non_diegetic_music:"]
    if mode == "i2va" and not text.startswith("For the target video"):
        findings.append(_finding("P1", "error", "I2VA is missing its instruction line.", "preview"))
    if mode == "fl2va" and "How the reference pictures align" not in text.split("\n", 1)[0]:
        findings.append(_finding("P1", "error", "FL2VA is missing its instruction line.", "preview"))
    if mode == "l2va" and "How the reference pictures align" not in text.split("\n", 1)[0]:
        findings.append(_finding("P1", "error", "L2VA is missing its instruction line.", "preview"))
    missing_headers = [h for h in required if h not in text]
    if missing_headers:
        findings.append(_finding("P1", "error", "Missing " + ", ".join(missing_headers), "preview"))

    defined = set()
    dupes = set()
    for row in attach:
        key = f"<{row['kind']} {row['label']}>"
        if key in defined:
            dupes.add(key)
        defined.add(key)
    for i, _ in enumerate(_subjects(clip), start=1):
        defined.add(f"<Subject {i}>")
    for lab in _labels_in(text):
        if lab not in defined:
            findings.append(_finding("P2", "error", f"{lab} is used and not defined.", "sec-cast"))
    for lab in sorted(dupes):
        findings.append(_finding("P2", "error", f"{lab} is used by more than one reference.", "sec-cast"))

    prev = -1.0
    shots = clip.get("shots") or []
    if not shots:
        findings.append(_finding("P3", "error", "Add at least one shot.", "sec-shots"))
    if duration > 0 and len(shots) > duration:
        findings.append(_finding("P3", "warn", f"{len(shots)} shots in {duration}s is tighter than one shot per second.", "sec-shots"))
    for i, shot in enumerate(shots, start=1):
        if i == 1:
            continue
        start = shot.get("startSec")
        try:
            start_f = float(start)
        except (TypeError, ValueError):
            findings.append(_finding("P3", "error", f"Shot {i} needs a start time.", f"shot-{i}"))
            continue
        if start_f <= prev or (duration > 0 and start_f >= duration):
            findings.append(_finding("P3", "error", f"Shot {i} starts at {start_f}, which is not strictly inside the clip after the previous cut.", f"shot-{i}"))
        prev = start_f

    for i, shot in enumerate(shots, start=1):
        move = (shot.get("cameraMove") or "").strip().lower()
        if not move:
            findings.append(_finding("P4", "error", f"Shot {i} has no camera move.", f"shot-{i}"))
            continue
        if not any(v in move for v in MOVE_VERBS):
            findings.append(_finding("P4", "error", f"Shot {i} move needs an official verb (push, pan, track, hold, zoom, …).", f"shot-{i}"))
        elif not any(v in move for v in STATIC_VERBS) and not any(w in f" {move} " for w in LANDING):
            findings.append(_finding("P4", "warn", f"Shot {i} move has no landing (toward, revealing, as, onto, keeping, while).", f"shot-{i}"))
        size = shot.get("size")
        angle = shot.get("angle")
        if size in WIDE_SIZES and angle in FACE_ANGLES:
            level = "error" if shot.get("lines") else "warn"
            findings.append(_finding("P5", level, f"Shot {i} is a {size} from the {angle}. A readable face belongs in a close-up, medium close-up, or medium.", f"shot-{i}"))
        if size in WIDE_SIZES and not shot.get("offscreenGuard"):
            findings.append(_finding("P9", "warn", f"Shot {i} is wide. Turn on “No other person” if the frame must not invent people.", f"shot-{i}"))

    speakers = speaker_map(clip)
    by_id = {s.get("id"): s for s in _subjects(clip)}
    seen_voice = {}
    for shot in shots:
        for line in shot.get("lines") or []:
            sub = by_id.get(line.get("subjectId"))
            if not (line.get("language") or "").strip() or not (line.get("native") or "").strip():
                findings.append(_finding("P7", "error", "A dialogue line needs a language and the spoken words.", "sec-shots"))
            if sub is None:
                continue
            phrase = voice_phrase(sub, voice_index_from(None))
            if sub.get("speaks") is False and not phrase:
                findings.append(_finding("P6", "warn", f"{sub.get('name') or 'A subject'} speaks without a voice phrase.", "sec-cast"))
            sid = sub.get("id")
            if sid in seen_voice and seen_voice[sid] != phrase:
                findings.append(_finding("P6", "warn", f"{speakers.get(sid)} voice wording changed between lines.", "sec-cast"))
            seen_voice[sid] = phrase
            if not sub.get("speaks") and sub.get("timbre") == "library" and not sub.get("voiceId"):
                findings.append(_finding("P6", "warn", "A speaking subject has no library voice.", "sec-cast"))

    if clip.get("audioPolicy") == "dialogue-only":
        if "overall_soundscape:\nN/A" not in text and "overall_soundscape: N/A" not in text:
            findings.append(_finding("P8", "error", "Dialogue only must set the soundscape to N/A.", "sec-sound"))
        if "non_diegetic_music:\nN/A" not in text and "non_diegetic_music: N/A" not in text:
            findings.append(_finding("P8", "error", "Dialogue only must set the music to N/A.", "sec-sound"))
        if CLOSING not in text:
            findings.append(_finding("P8", "error", "Dialogue only must end the opening with the house-audio sentence.", "sec-meta"))
    if mode == "ref2va" and clip.get("style") != "generic" and not (clip.get("styleOpening") or "").strip():
        findings.append(_finding("P8", "error", "Ref2VA needs a style opening before Shot 1.", "sec-meta"))
    for row in attach:
        if row.get("missing"):
            findings.append(_finding("file", "warn", f"{row['kind']} {row['label']} ({row['role']}) has no file.", "sec-cast"))
    if mode == "ref2va" and not (clip.get("summary") or "").strip():
        findings.append(_finding("P2", "warn", "The summary paragraph is empty.", "sec-summary"))
    if mode == "ref2va" and not studio.effective_tasks(clip):
        findings.append(_finding("P2", "warn", "Pick at least one summary task type.", "sec-summary"))
    findings.extend(studio.extra_findings(clip, text))
    return findings


def clip_filename(clip: dict, number: int) -> str:
    return f"clip-{number:02d}-{int(clip.get('durationSec') or 0)}s.txt"


def file_text(clip: dict, body: str) -> str:
    headers = clip.get("headers") or {}
    lines = []
    for key, field in (("handoff-from", "handoffFrom"), ("end-frame", "endFrame"), ("next", "next")):
        value = (headers.get(field) or "").strip()
        if value:
            lines.append(f"{key}: {value}")
    body = body.strip() + "\n"
    if lines:
        return "\n".join(lines) + "\n\n" + body
    return body


def plates_text(clips: list, scene_comment: str = "") -> str:
    out = [studio.plates_header(clips, scene_comment)]
    for i, clip in enumerate(clips, start=1):
        if (clip.get("platesComment") or "").strip():
            out.extend(clip["platesComment"].strip().splitlines())
        out.append(f"# clip-{i:02d}  {int(clip.get('durationSec') or 0)}s  {clip.get('mode')}  {clip.get('title') or ''}".rstrip())
        for n, row in enumerate(attach_order(clip), start=1):
            out.append("\t".join([
                str(n),
                f"{row['kind']} {row['label']}",
                row.get("role") or "",
                row.get("name") or "",
                row.get("file") or "MISSING",
            ]))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


_HEADER = re.compile(r"^(handoff-from|end-frame|next):\s*(.*)$", re.I)


def _strip_headers(text: str) -> tuple[str, dict]:
    headers = {"handoffFrom": "", "endFrame": "", "next": ""}
    keymap = {"handoff-from": "handoffFrom", "end-frame": "endFrame", "next": "next"}
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (_HEADER.match(lines[i]) or lines[i].strip() == ""):
        m = _HEADER.match(lines[i])
        if m:
            headers[keymap[m.group(1).lower()]] = m.group(2).strip()
        elif lines[i].strip() == "" and i > 0:
            i += 1
            break
        i += 1
    return "\n".join(lines[i:]), headers


def import_prompt(text: str, mode_hint: str = "ref2va") -> dict:
    body, headers = _strip_headers(text.strip())
    low = body.lower()
    if "subject_definitions:" in low:
        mode = "ref2va"
    elif low.startswith("for the target video"):
        mode = "i2va"
    elif low.startswith("how the reference pictures align") and "<picture" in low.split("\n", 1)[0].lower():
        mode = "l2va"
    elif low.startswith("how the reference pictures align"):
        mode = "fl2va"
    elif mode_hint in ("t2va", "i2va", "fl2va", "l2va", "ref2va"):
        mode = mode_hint
    else:
        mode = "t2va"
    clip = new_clip(mode)
    clip["headers"] = headers
    clip["subjects"] = []
    clip["shots"] = []
    notes = []

    if mode == "ref2va":
        parts = re.split(r"\n(?=(?:subject_definitions|summary|retention_analysis|detailed_description|overall_soundscape|non_diegetic_music):)", body)
        blocks = {}
        for part in parts:
            if ":" not in part:
                notes.append(part)
                continue
            name, _, rest = part.partition(":")
            blocks[name.strip()] = rest.strip()
        parsed_subjects, extras, anchors = studio.parse_definitions(blocks.get("subject_definitions", ""))
        for row in parsed_subjects:
            sub = new_subject()
            sub["name"] = row["name"]
            sub["description"] = row["description"]
            sub["imageLabel"] = row["imageLabel"]
            sub["identityOnly"] = row["identityOnly"]
            clip["subjects"].append(sub)
        clip["extras"] = extras
        clip["anchors"] = anchors
        summary = blocks.get("summary", "")
        tm = re.match(r"\[([^\]]+)\]\s*(.*)", summary, re.S)
        if tm:
            clip["taskTypes"] = [t.strip() for t in tm.group(1).split("+")]
            clip["summary"] = tm.group(2).strip()
        else:
            clip["summary"] = summary
        detail = blocks.get("detailed_description", "")
        if detail and not detail.startswith("[Shot"):
            first, _, rest = detail.partition("[Shot")
            clip["styleOpening"] = first.strip()
            detail = ("[Shot" + rest) if rest else ""
        _shots_from_text(clip, detail)
        sound = blocks.get("overall_soundscape", "N/A")
        music = blocks.get("non_diegetic_music", "N/A")
    else:
        instr, _, rest = body.partition("integrated_multimodal_description:")
        if instr.strip() and mode == "t2va":
            notes.append(instr.strip())
        field, _, tail = rest.partition("overall_soundscape:")
        sound_part, _, music_part = tail.partition("non_diegetic_music:")
        sound = sound_part.strip()
        music = music_part.strip()
        _shots_from_text(clip, field.strip())
        if not clip["subjects"]:
            sub = new_subject()
            sub["name"] = "the woman"
            clip["subjects"] = [sub]

    if sound.strip() == "N/A" and music.strip() == "N/A":
        clip["audioPolicy"] = "dialogue-only"
    else:
        clip["audioPolicy"] = "full"
        clip["soundscape"] = sound
        clip["music"] = music
    if CLOSING in (clip.get("styleOpening") or ""):
        clip["styleOpening"] = clip["styleOpening"].replace(CLOSING, "").strip()
    if not clip["shots"]:
        clip["shots"] = [new_shot(1, clip["durationSec"])]
        notes.append(body)
    clip["notes"] = "\n".join(n for n in notes if n.strip())
    if mode == "ref2va" and blocks.get("retention_analysis"):
        parsed_rows = studio.parse_retention(blocks["retention_analysis"])
        clip["retention"] = parsed_rows or sync_retention(clip)
    else:
        clip["retention"] = sync_retention(clip)
    return clip


def _shots_from_text(clip: dict, detail: str) -> None:
    chunks = re.split(r"(?=\[Shot \d+\])", detail)
    for chunk in chunks:
        m = re.match(r"\[Shot (\d+)\]\s*(.*)", chunk, re.S)
        if not m:
            continue
        body = m.group(2).strip()
        shot = new_shot(int(m.group(1)), clip["durationSec"])
        tm = re.match(r"At (\d\d):(\d\d)\.(\d\d\d),\s*(?:the (?:camera|shot) cuts to\s*)?(.*)", body, re.S)
        if tm:
            shot["startSec"] = int(tm.group(1)) * 60 + int(tm.group(2)) + int(tm.group(3)) / 1000
            body = tm.group(4).strip()
        lines = studio.extract_lines(body, clip.get("subjects") or [])
        spoken = re.sub(r"\s*<d>.*?</d>", "", body)
        spoken = re.sub(
            r"\s*(?:<Subject \d+>|[A-Z][^.<]{0,60}) \(S\d+\) says .*?(?=(?:<Subject \d+>|[A-Z][^.<]{0,60}) \(S\d+\) says |\Z)",
            " ",
            spoken,
            flags=re.S,
        )
        spoken = re.sub(r"<scenetrans>.*", "", spoken)
        spoken = re.sub(r"<cutoff>", "", spoken)
        parsed = studio.parse_shot_fields(spoken)
        shot.update({k: parsed[k] for k in (
            "size", "angle", "lens", "cameraMove", "offscreenGuard", "eyeline",
            "onScreenText", "onScreenReadable", "custom", "text",
        )})
        if not shot["cameraMove"]:
            shot["cameraMove"] = "holds a static shot"
        have = {(a.get("imageLabel"), a.get("shot"), a.get("kind")) for a in clip.get("anchors") or []}
        for anchor in parsed.get("anchors") or []:
            key = (anchor["imageLabel"], int(m.group(1)), anchor["kind"])
            if key in have:
                continue
            clip.setdefault("anchors", []).append({
                "imageLabel": anchor["imageLabel"],
                "shot": key[1],
                "kind": anchor["kind"],
                "note": "parsed from the shot",
            })
            have.add(key)
        shot["lines"] = lines
        clip["shots"].append(shot)


def import_scene(folder: str | Path) -> list:
    root = Path(folder)
    files = sorted(root.glob("clip-*.txt"))
    plates = (root / "PLATES.txt").read_text(encoding="utf-8") if (root / "PLATES.txt").is_file() else ""
    blocks = re.split(r"(?m)^#\s*clip-(\d+)", plates)
    plate_map = {}
    # split keeps the captured number between chunks: ['pre', '01', 'body', '02', 'body']
    it = iter(blocks[1:])
    for num, body in zip(it, it):
        paths = []
        for line in body.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) >= 5:
                paths.append(cols[-1].strip())
            elif len(cols) >= 2 and cols[-1].startswith("/"):
                paths.append(cols[-1].strip())
        plate_map[int(num)] = [p for p in paths if p and p != "MISSING"]
    clips = []
    for path in files:
        m = re.search(r"clip-(\d+)-(\d+)s", path.name)
        number = int(m.group(1)) if m else len(clips) + 1
        duration = int(m.group(2)) if m else 8
        clip = import_prompt(path.read_text(encoding="utf-8"))
        clip["durationSec"] = duration
        clip["title"] = path.stem
        files_for = plate_map.get(number, [])
        fi = 0
        for sub in clip["subjects"]:
            if fi < len(files_for):
                sub["imageFile"] = files_for[fi]
                fi += 1
        if clip["mode"] in ("i2va", "fl2va") and files_for:
            clip["frames"]["first"] = files_for[0]
        if clip["mode"] in ("fl2va", "l2va") and files_for:
            clip["frames"]["last"] = files_for[-1]
        clips.append(clip)
    return clips


def assemble(clip: dict, bank: dict | None = None) -> dict:
    text = render_clip(clip, bank)
    findings = validate_clip(clip, text, bank)
    findings.extend(studio.clip_file_findings(clip))
    return {
        "text": text,
        "body": text.strip(),
        "findings": findings,
        "attach": attach_order(clip),
        "speakers": speaker_map(clip),
        "chars": len(text.strip()),
        "words": studio.word_count(text),
        "payload": studio.api_payload(clip, text),
    }


def self_test() -> None:
    bank = banks()
    # Ref2VA dialogue-only six sections
    clip = new_clip("ref2va")
    clip["title"] = "Balcony"
    sub = clip["subjects"][0]
    sub["name"] = "the woman"
    sub["gender"] = "female"
    sub["speaks"] = True
    sub["voiceId"] = "F5"
    sub["imageFile"] = "/tmp/woman.png"
    clip["summary"] = "She turns toward the lens."
    clip["taskTypes"] = ["reference generation", "keyframe completion"]
    clip["anchors"] = [{"imageLabel": 1, "shot": 1, "kind": "composition", "note": "defining her at the rail"}]
    clip["shots"][0]["text"] = "She stands at the rail, mouth closed, eyes on the lens."
    clip["shots"][0]["lines"] = [{
        "subjectId": sub["id"], "language": "English", "native": "Wait.",
        "delivery": "", "closeMouth": True, "continuation": None,
    }]
    clip["retention"] = sync_retention(clip)
    out = assemble(clip, bank)
    text = out["text"]
    for header in ("subject_definitions:", "summary:", "retention_analysis:", "detailed_description:", "overall_soundscape:", "non_diegetic_music:"):
        assert header in text, header
    assert "[reference generation + keyframe completion]" in text
    assert "overall_soundscape:\nN/A" in text
    assert CLOSING in text
    assert "<Subject 1> (S1) says" in text
    assert "<d>[English] Wait.</d>" in text
    assert "She closes her lips." in text
    assert "(S1)" not in text.split("retention_analysis:")[1].split("detailed_description:")[0]
    assert not any(f["severity"] == "error" for f in out["findings"]), out["findings"]

    # Second speaker is S2, first stays S1
    other = new_subject()
    other["name"] = "the man"
    other["gender"] = "male"
    other["imageLabel"] = 2
    other["imageFile"] = "/tmp/man.png"
    other["speaks"] = True
    other["voiceId"] = "M1"
    clip["subjects"].append(other)
    clip["shots"].append(new_shot(2, 8))
    clip["shots"][1]["startSec"] = 4
    clip["shots"][1]["lines"] = [{
        "subjectId": other["id"], "language": "Hindi", "native": "रuko.",
        "delivery": "", "closeMouth": True, "continuation": None,
    }]
    clip["retention"] = sync_retention(clip)
    text = render_clip(clip, bank)
    assert "<Subject 2> (S2) says" in text
    assert "in a deep, gravelly middle-aged male voice" in text

    # Five modes, instruction lines
    for mode, needle in (
        ("t2va", "integrated_multimodal_description:"),
        ("i2va", "For the target video, at 0.00 seconds"),
        ("fl2va", "Picture 1 (from Shot 1)"),
        ("l2va", "<Picture 1> (from [Shot 1])"),
    ):
        c = new_clip(mode)
        if mode == "fl2va":
            c["frames"] = {"first": "/tmp/a.png", "last": "/tmp/b.png"}
        elif mode == "i2va":
            c["frames"] = {"first": "/tmp/a.png", "last": ""}
        elif mode == "l2va":
            c["frames"] = {"first": "", "last": "/tmp/b.png"}
        rendered = render_clip(c, bank)
        assert needle in rendered, (mode, rendered[:200])
        assert "overall_soundscape: N/A" in rendered
        if mode == "t2va":
            assert not rendered.startswith("For ") and not rendered.startswith("How ")
        if mode == "fl2va":
            assert "<Picture" not in rendered.split("\n", 1)[0]

    # Limits fire
    bad = new_clip("t2va")
    bad["durationSec"] = 3
    bad["ratio"] = "adaptive"
    bad["resolution"] = "480P"
    findings = {f["id"] for f in validate_clip(bad, render_clip(bad, bank), bank)}
    assert {"L1", "L2", "L3"} <= findings, findings

    # Import keeps the line
    imported = import_prompt(text)
    assert imported["mode"] == "ref2va"
    assert any("Wait." in (ln.get("native") or "") or "रuko." in (ln.get("native") or "") for s in imported["shots"] for ln in s["lines"])

    # Deterministic
    assert render_clip(clip, bank) == render_clip(clip, bank)
    studio.self_test()
    print("ok  engine self-test")


if __name__ == "__main__":
    self_test()
