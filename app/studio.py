"""Scene, timeline, continuity, fixes, and file probes for the editor.

Pure helpers. The renderer in engine.py calls the small pieces it needs.
"""

from __future__ import annotations

import base64
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
STYLES_EXTRA = ROOT / "meta-prompts" / "styles-extra.json"
CHEATSHEETS = ROOT / "cheatsheets"

ACCENTS = [
    "with a light Indian English accent",
    "speaking Kannada with a natural Bengaluru urban accent",
    "speaking Kannada with a rustic North Karnataka accent",
    "speaking Kannada with a soft Mysuru accent",
    "speaking Hindi with a Mumbai street accent",
    "speaking formal, theatrical Hindi",
    "speaking Tamil with a Chennai accent",
    "speaking Telugu with a Hyderabad accent",
    "speaking Malayalam with a soft Kerala lilt",
    "with a neutral American accent",
    "with a British accent",
]

READY_LINES = {
    "Go inside.": {"Kannada": "ಒಳಗೆ ಹೋಗು.", "Hindi": "अंदर जाओ.", "Tamil": "உள்ளே போ.", "Telugu": "లోపలికి వెళ్ళు.", "Malayalam": "അകത്തേക്ക് പോ."},
    "Come here.": {"Kannada": "ಇಲ್ಲಿ ಬಾ.", "Hindi": "इधर आओ.", "Tamil": "இங்கே வா.", "Telugu": "ఇక్కడికి రా.", "Malayalam": "ഇവിടെ വാ."},
    "Stop!": {"Kannada": "ನಿಲ್ಲು!", "Hindi": "रुको!", "Tamil": "நில்!", "Telugu": "ఆగు!", "Malayalam": "നിൽക്ക്!"},
    "Tell the truth.": {"Kannada": "ಸತ್ಯ ಹೇಳು.", "Hindi": "सच बताओ.", "Tamil": "உண்மையைச் சொல்.", "Telugu": "నిజం చెప్పు.", "Malayalam": "സത്യം പറ."},
    "Forgive me.": {"Kannada": "ನನ್ನನ್ನು ಕ್ಷಮಿಸಿ.", "Hindi": "मुझे माफ़ कर दो.", "Tamil": "என்னை மன்னித்துவிடு.", "Telugu": "నన్ను క్షమించు.", "Malayalam": "എന്നോട് ക്ഷമിക്കൂ."},
    "Keep quiet.": {"Kannada": "ಸುಮ್ಮನಿರು.", "Hindi": "चुप रहो.", "Tamil": "பேசாமல் இரு.", "Telugu": "నోరు మూసుకో.", "Malayalam": "മിണ്ടാതിരിക്ക്."},
}
POLITE_KANNADA = {"ಒಳಗೆ ಹೋಗು.": "ಒಳಗೆ ಹೋಗಿ.", "ಇಲ್ಲಿ ಬಾ.": "ಇಲ್ಲಿ ಬನ್ನಿ."}

BEATS = {
    "line": ("hold", "", "", "as the line is spoken"),
    "confession": ("push", "small", "slow", "toward the face"),
    "order": ("hold", "", "", ""),
    "shock": ("zoom-in", "large", "fast", "onto the face"),
    "walk": ("track", "", "slow", "from the front, keeping a steady distance"),
    "escort": ("track", "", "slow", "from behind"),
    "door": ("hold", "", "", "as the door opens"),
    "reveal": ("pan-right", "large", "slow", "revealing the room"),
    "romance": ("arc", "small", "slow", "around them"),
    "chase": ("track", "", "fast", "from behind"),
    "impact": ("shake-strong", "", "", ""),
    "nervous": ("shake-slight", "", "", ""),
    "pov": ("pov", "", "", ""),
    "ending": ("pull", "", "slow", "revealing the space behind"),
}

VERBS = {
    "hold": "holds a static shot",
    "push": "pushes in",
    "pull": "pulls out",
    "zoom-in": "zooms in",
    "zoom-out": "zooms out",
    "pan-left": "pans left",
    "pan-right": "pans right",
    "tilt-up": "tilts up",
    "tilt-down": "tilts down",
    "truck-left": "trucks left",
    "truck-right": "trucks right",
    "pedestal-up": "pedestals up",
    "pedestal-down": "pedestals down",
    "arc": "arcs around",
    "track": "tracks",
    "pov": "holds the point of view",
    "shake-slight": "shakes slightly",
    "shake-strong": "shakes strongly",
    "roll-cw": "rolls clockwise",
    "roll-ccw": "rolls counterclockwise",
}
QUIET_VERBS = {"hold", "pov", "shake-slight", "shake-strong"}
WIDE = {"wide", "extreme wide", "establishing", "medium-wide"}
FACE_SIZES = {"close-up", "medium close-up", "medium"}
FACE_ANGLES = {"front", "three-quarter"}
FACE_WORDS = ("brow", "smile", "eyes", "mouth", "lips", "frown", "gaze", "expression")
SOUND_WORDS = ("music", "ambience", "footstep", "score", "rain", "murmur", "soundtrack")
BAD_TAGS = ("4k", "masterpiece", "best quality", "ultra-detailed")
SUBTITLE_WORDS = ("subtitle", "subtitles", "lower third", "burned-in caption", "burnt-in caption")
HEAD_TOKENS = ("lipstick", "eyeshadow", "mascara", "eyeliner", "blush", "bindi", "glasses", "pigtail", "braid")
MOVE_WORDS = ("push", "pull", "zoom", "pan", "tilt", "truck", "pedestal", "arc", "track", "shake", "roll", "hold", "pov")


def catalog() -> dict:
    return {
        "accents": ACCENTS,
        "readyLines": READY_LINES,
        "politeKannada": POLITE_KANNADA,
        "beats": list(BEATS),
        "moveVerbs": [{"id": k, "phrase": v} for k, v in VERBS.items()],
        "statuses": ["draft", "checked", "locked", "rendered", "rejected"],
        "templates": ["single", "reverse", "escort", "door", "reaction", "montage"],
        "clipKinds": ["narrative", "sampler"],
    }


def prepare_clip(clip: dict) -> dict:
    clip.setdefault("status", "draft")
    clip.setdefault("clipKind", "narrative")
    clip.setdefault("sceneId", "sc-default")
    clip.setdefault("autoTasks", True)
    clip.setdefault("endState", "")
    clip.setdefault("lightLock", False)
    clip.setdefault("facts", "")
    clip.setdefault("carried", "")
    clip.setdefault("renderPath", "")
    clip.setdefault("variantOf", "")
    clip.setdefault("variantName", "")
    clip.setdefault("platesComment", "")
    clip.setdefault("rejectReason", "")
    clip.setdefault("screenDirection", "")
    clip.setdefault("ambience", "")
    clip.setdefault("foley", "")
    clip.setdefault("humanSounds", "")
    clip.setdefault("frameNote", "")
    clip.setdefault("allowCuts", False)
    for sub in clip.get("subjects") or []:
        sub.setdefault("identityLock", False)
        sub.setdefault("identityOnly", False)
        sub.setdefault("turnaround", False)
        sub.setdefault("accent", "")
        sub.setdefault("libraryId", "")
        sub.setdefault("transcript", "")
    for extra in clip.get("extras") or []:
        extra.setdefault("fileMtime", None)
    for shot in clip.get("shots") or []:
        shot.setdefault("expression", "")
        shot.setdefault("eyeline", "")
        shot.setdefault("onScreenText", "")
        shot.setdefault("onScreenReadable", True)
        shot.setdefault("diegetic", "")
        shot.setdefault("beat", "")
        shot.setdefault("folded", False)
        shot.setdefault("visible", [])
        shot.setdefault("moveParts", {"verb": "hold", "amplitude": "", "speed": "", "landing": ""})
        for line in shot.get("lines") or []:
            line.setdefault("voiceover", False)
            line.setdefault("register", "")
    return clip


def prepare_project(project: dict) -> dict:
    project["schemaVersion"] = 2
    project.setdefault("houseAudio", "dialogue-only")
    project.setdefault("screenDirection", "ltr")
    project.setdefault("library", {"cast": [], "locations": []})
    clips = project.setdefault("clips", [])
    for clip in clips:
        prepare_clip(clip)
    scenes = project.get("scenes") or []
    if not scenes:
        scenes = [{
            "id": "sc-default",
            "title": "Scene 1",
            "notes": "",
            "platesComments": "",
            "clipIds": [c.get("id") for c in clips],
        }]
    known = []
    for scene in scenes:
        scene.setdefault("notes", "")
        scene.setdefault("platesComments", "")
        scene["clipIds"] = [i for i in (scene.get("clipIds") or []) if any(c.get("id") == i for c in clips)]
        known.extend(scene["clipIds"])
    have = set(known)
    for clip in clips:
        if clip.get("id") not in have:
            scenes[0]["clipIds"].append(clip.get("id"))
            clip["sceneId"] = scenes[0]["id"]
    project["scenes"] = scenes
    return project


def build_move(parts: dict, label: str = "") -> str:
    kind = (parts or {}).get("verb") or "hold"
    phrase = VERBS.get(kind, VERBS["hold"])
    if kind not in QUIET_VERBS:
        bits = []
        amp = (parts or {}).get("amplitude") or ""
        speed = (parts or {}).get("speed") or ""
        if amp in ("small", "large"):
            bits.append(f"with {amp} amplitude")
        if speed in ("slow", "fast"):
            bits.append(f"at {speed} speed")
        if bits:
            phrase += " " + " ".join(bits)
    landing = ((parts or {}).get("landing") or "").strip()
    if kind in ("track", "arc") and label and label not in landing:
        phrase += f" {label}"
    if landing:
        phrase += " " + landing.lstrip()
    return phrase.strip()


def beat_parts(beat: str, style: str) -> dict:
    verb, amp, speed, landing = BEATS.get(beat, BEATS["line"])
    if beat == "shock" and style != "80s-bollywood":
        verb, amp, speed, landing = "push", "small", "fast", "toward the face"
    return {"verb": verb, "amplitude": amp, "speed": speed, "landing": landing}


def line_seconds(line: dict) -> float:
    native = (line.get("native") or "").strip()
    if not native:
        return 0.8
    lang = line.get("language") or "English"
    if lang == "English":
        words = max(1, len(native.split()))
        return words / 2.5
    chars = max(1, len(re.sub(r"\s+", "", native)))
    return chars / 4.5


def shot_min_seconds(shot: dict) -> float:
    lines = [ln for ln in (shot.get("lines") or []) if (ln.get("native") or "").strip()]
    if lines:
        return sum(line_seconds(ln) for ln in lines) + 1.0 + 0.5
    if (shot.get("text") or "").strip():
        return 2.5
    return 1.5


def shot_budget(duration: int) -> tuple[int, int]:
    if duration <= 6:
        return 1, 2
    if duration <= 10:
        return 2, 3
    return 3, 4


def auto_task_types(clip: dict) -> list[str]:
    tasks = []
    if clip.get("mode") == "ref2va":
        tasks.append("reference generation")
    if clip.get("anchors"):
        tasks.append("keyframe completion")
    for video in clip.get("videos") or []:
        intent = video.get("intent") or "camera"
        if intent == "edit":
            tasks.append("video editing")
        elif intent == "continuation":
            tasks.append("video continuation")
    for sub in clip.get("subjects") or []:
        if sub.get("speaks") and sub.get("timbre") == "audio" and sub.get("audioFile"):
            tasks.append("audio reuse" if sub.get("audioReuse") else "audio reference")
    return list(dict.fromkeys(tasks))


def effective_tasks(clip: dict) -> list[str]:
    chosen = [t for t in (clip.get("taskTypes") or []) if t]
    if clip.get("autoTasks", True):
        return list(dict.fromkeys(chosen + auto_task_types(clip)))
    return list(dict.fromkeys(chosen))


def word_count(text: str) -> int:
    detail = ""
    if "detailed_description:" in text:
        detail = text.split("detailed_description:", 1)[1].split("overall_soundscape:", 1)[0]
    elif "integrated_multimodal_description:" in text:
        detail = text.split("integrated_multimodal_description:", 1)[1].split("overall_soundscape:", 1)[0]
    return len(re.findall(r"[A-Za-z0-9']+", detail))


def _finding(fid, severity, message, focus, fix=None) -> dict:
    row = {"id": fid, "severity": severity, "message": message, "focus": focus}
    if fix:
        row["fix"] = fix
    return row


def extra_findings(clip: dict, text: str) -> list[dict]:
    out = []
    mode = clip.get("mode")
    shots = clip.get("shots") or []
    try:
        duration = int(clip.get("durationSec") or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration:
        _rec, limit = shot_budget(duration)
        if len(shots) > limit:
            out.append(_finding("budget", "warn", f"{len(shots)} shots in {duration}s is past the usual maximum of {limit}.", "sec-shots", "reflow"))
    if shots:
        span = 0.0
        for i, shot in enumerate(shots):
            start = 0.0 if i == 0 else float(shot.get("startSec") or 0)
            end = duration if i == len(shots) - 1 else float((shots[i + 1].get("startSec") if i + 1 < len(shots) else duration) or duration)
            if i == len(shots) - 1:
                end = float(duration)
            elif i + 1 < len(shots) and shots[i + 1].get("startSec") is not None:
                end = float(shots[i + 1]["startSec"])
            length = max(0.0, end - start)
            need = shot_min_seconds(shot)
            if length + 0.05 < need and (shot.get("lines") or shot.get("text")):
                out.append(_finding("time", "warn", f"Shot {i + 1} is about {length:.1f}s and the line or action wants about {need:.1f}s.", f"shot-{i + 1}", "reflow"))
            spoken = sum(line_seconds(ln) for ln in (shot.get("lines") or []))
            if spoken and spoken > length + 0.2:
                out.append(_finding("time", "error", f"Shot {i + 1} has about {spoken:.1f}s of speech in a {length:.1f}s shot.", f"shot-{i + 1}", "reflow"))
            span = end
        if duration and not (shots[-1].get("text") or "").strip() and not (shots[-1].get("lines") or []):
            out.append(_finding("ending", "warn", "The last shot does not describe what happens through the end of the clip.", f"shot-{len(shots)}"))
        del span
    for i, shot in enumerate(shots, start=1):
        move = (shot.get("cameraMove") or "").lower()
        hits = [w for w in MOVE_WORDS if w in move]
        if "hold" in hits and len(hits) > 1:
            hits = [w for w in hits if w != "hold"]
        if len(hits) > 1:
            out.append(_finding("move", "error", f"Shot {i} has more than one camera move ({', '.join(hits)}). Split it.", f"shot-{i}"))
        size = shot.get("size")
        angle = shot.get("angle")
        readable = size in FACE_SIZES and angle in FACE_ANGLES
        if readable and any(w in move for w in ("pull", "zoom out", "zooms out", "pedestal up", "pedestals up")):
            out.append(_finding("face", "error", f"Shot {i} pulls or rises off a readable face. Put the wide in the next shot, from behind.", f"shot-{i}"))
        if (shot.get("lens") or "") in ("24mm", "wide-angle") and readable:
            out.append(_finding("lens", "warn", f"Shot {i} uses a wide lens on a readable face.", f"shot-{i}"))
        blob = f"{shot.get('text') or ''} {shot.get('expression') or ''}".lower()
        if readable and not any(w in blob for w in FACE_WORDS):
            out.append(_finding("expr", "warn", f"Shot {i} has a readable face and no expression.", f"shot-{i}"))
        if "fast" in move and size in WIDE:
            out.append(_finding("speed", "warn", f"Shot {i} is a fast wide. Keep the camera slow and let the subject move.", f"shot-{i}"))
        if "track" in move and readable and "steady distance" not in move:
            out.append(_finding("track", "warn", f"Shot {i} tracks a face without a steady distance.", f"shot-{i}", "tracking"))
        sign = shot.get("onScreenText") or ""
        if sign and len(sign.split()) > 3:
            out.append(_finding("sign", "warn", f"Shot {i} sign is longer than three words and may render as gibberish.", f"shot-{i}"))
        low = blob + " " + (shot.get("diegetic") or "").lower()
        if any(w in low for w in SUBTITLE_WORDS):
            out.append(_finding("sub", "warn", f"Shot {i} asks for subtitles. Add those in the edit.", f"shot-{i}"))
        if clip.get("audioPolicy") == "dialogue-only":
            prose = (shot.get("text") or "").lower()
            if any(w in prose for w in SOUND_WORDS):
                out.append(_finding("snd", "warn", f"Shot {i} mentions sound while the clip is dialogue-only.", f"shot-{i}", "strip-sound"))
        if clip.get("clipKind") == "sampler" and size in WIDE:
            if any(tok in blob for tok in HEAD_TOKENS):
                out.append(_finding("sampler", "warn", f"Shot {i} describes hair, makeup, or glasses in a full-body sampler. Those words pull the crop to a close-up.", f"shot-{i}"))
        for line in shot.get("lines") or []:
            native = line.get("native") or ""
            if "।" in native:
                out.append(_finding("punct", "warn", f"Shot {i} uses a danda. End the line with . ? or !.", f"shot-{i}", "danda"))
            if native and native[-1] not in ".?!":
                out.append(_finding("punct", "warn", f"Shot {i} line does not end with . ? or !.", f"shot-{i}"))
            if line.get("continuation") == "cutoff" and i != len(shots):
                out.append(_finding("cut", "warn", f"<cutoff> is on shot {i}, not the last shot.", f"shot-{i}"))
    joined = "\n".join((s.get("text") or "") for s in shots)
    if re.search(r"[\u0C80-\u0CFF\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F\u0D00-\u0D7F]", joined):
        out.append(_finding("script", "warn", "Action text contains a non-Latin script. Keep that script inside <d> or a quoted sign.", "sec-shots"))
    low_text = text.lower()
    if any(tag in low_text for tag in BAD_TAGS):
        out.append(_finding("tags", "warn", "The prompt contains quality tags. Describe the light and the materials instead.", "sec-meta"))
    if mode == "ref2va":
        words = word_count(text)
        if words and words < 80:
            out.append(_finding("words", "warn", f"The description is about {words} words. A generation clip is usually 350–500 when the lines allow it.", "preview"))
        if clip.get("lightLock"):
            files = [s.get("imageFile") for s in (clip.get("subjects") or []) if s.get("imageFile")]
            files += [e.get("file") for e in (clip.get("extras") or []) if e.get("file")]
            if len(files) > 1:
                out.append(_finding("light", "warn", "Light lock is on and more than one plate is attached. A second plate can bring its own grade.", "sec-cast"))
        for sub in clip.get("subjects") or []:
            if sub.get("turnaround"):
                out.append(_finding("sheet", "warn", f"{sub.get('name') or 'A subject'} is marked as a multi-panel sheet. The output tends to reproduce the panels. Use a single-view plate.", "sec-cast"))
            if sub.get("identityLock"):
                desc = f"{sub.get('description') or ''} {joined}".lower()
                if any(w in desc for w in ("blonde", "ponytail", "red dress", "lipstick", "curly hair")):
                    out.append(_finding("ident", "warn", f"{sub.get('name') or 'A subject'} is identity-locked, and the text invents hair, makeup, or wardrobe.", "sec-cast"))
            transcript = (sub.get("transcript") or "").strip()
            if transcript and sub.get("timbre") == "audio" and not sub.get("audioReuse") and transcript[:24] in text:
                out.append(_finding("audio", "warn", "The audio transcript appears in the prompt. Timbre reference should not copy the original words.", "sec-cast"))
    if mode == "fl2va" and len(shots) > 1 and not clip.get("allowCuts"):
        out.append(_finding("fl2", "warn", "FL2VA usually stays one shot so the frames can interpolate. Turn on cuts only when you need them.", "sec-frames"))
    opening = (clip.get("styleOpening") or "").lower()
    if any(w in opening for w in MOVE_WORDS if w != "hold"):
        if "camera" in opening or "push" in opening or "pan" in opening:
            out.append(_finding("style", "warn", "The style opening contains a camera move. Keep the move on the shot.", "sec-meta"))
    return out


def apply_fix(clip: dict, fix: str) -> dict:
    prepare_clip(clip)
    if fix == "reflow":
        weights = [shot_min_seconds(s) for s in clip.get("shots") or []]
        total = sum(weights) or 1
        dur = float(clip.get("durationSec") or 8)
        acc = 0.0
        for i, shot in enumerate(clip.get("shots") or []):
            if i == 0:
                shot["startSec"] = None
            else:
                shot["startSec"] = round(dur * acc / total, 3)
            acc += weights[i]
    elif fix == "wide-guard":
        for shot in clip.get("shots") or []:
            if shot.get("size") in WIDE:
                shot["offscreenGuard"] = True
    elif fix == "tasks":
        clip["taskTypes"] = effective_tasks(clip)
    elif fix == "mouth":
        for shot in clip.get("shots") or []:
            for line in shot.get("lines") or []:
                if not line.get("voiceover"):
                    line["closeMouth"] = True
    elif fix == "tracking":
        for shot in clip.get("shots") or []:
            move = shot.get("cameraMove") or ""
            if "track" in move.lower() and "steady distance" not in move.lower():
                shot["cameraMove"] = move.rstrip(".") + ", keeping a steady distance"
    elif fix == "danda":
        for shot in clip.get("shots") or []:
            for line in shot.get("lines") or []:
                line["native"] = (line.get("native") or "").replace("।", ".")
    elif fix == "strip-sound":
        for shot in clip.get("shots") or []:
            text = shot.get("text") or ""
            for word in ("music", "ambience", "footsteps", "score", "soundtrack"):
                text = re.sub(rf"\b{word}\b", "", text, flags=re.I)
            shot["text"] = re.sub(r"\s{2,}", " ", text).strip()
    elif fix == "time-typo":
        for shot in clip.get("shots") or []:
            shot["text"] = re.sub(r"(\d\d:\d\d):(\d{3})", r"\1.\2", shot.get("text") or "")
    elif fix == "retention-speaker":
        for row in clip.get("retention") or []:
            row["note"] = re.sub(r"\s*\(S\d+\)", "", row.get("note") or "")
    elif fix == "house":
        from engine import CLOSING
        opening = (clip.get("styleOpening") or "").strip()
        if clip.get("audioPolicy") == "dialogue-only" and CLOSING not in opening:
            clip["styleOpening"] = (opening.rstrip(".") + ". " + CLOSING).strip()
    elif fix == "single-figure":
        sentence = (
            "Each shot holds exactly one view of the subject and no other person. "
            "Angles are separated by cuts, never combined in one frame."
        )
        opening = clip.get("styleOpening") or ""
        if "exactly one view" not in opening:
            clip["styleOpening"] = (opening.rstrip(".") + ". " + sentence).strip()
    return clip


def duplicate_clip(clip: dict, variant: bool = False) -> dict:
    fresh = copy.deepcopy(clip)
    fresh["id"] = "c" + _token()
    id_map = {}
    for sub in fresh.get("subjects") or []:
        new_id = "s" + _token()
        id_map[sub.get("id")] = new_id
        sub["id"] = new_id
    for shot in fresh.get("shots") or []:
        for line in shot.get("lines") or []:
            line["subjectId"] = id_map.get(line.get("subjectId"), line.get("subjectId"))
    fresh["status"] = "draft"
    fresh["renderPath"] = ""
    if variant:
        fresh["variantOf"] = clip.get("id")
        fresh["variantName"] = fresh.get("variantName") or "variant"
        fresh["title"] = (clip.get("title") or "Clip") + " variant"
    else:
        fresh["variantOf"] = ""
        fresh["title"] = (clip.get("title") or "Clip") + " copy"
    return fresh


def split_clip(clip: dict, at: int) -> tuple[dict, dict]:
    shots = clip.get("shots") or []
    at = max(1, min(at, len(shots) - 1))
    left = duplicate_clip(clip)
    right = duplicate_clip(clip)
    left["shots"] = copy.deepcopy(shots[:at])
    right["shots"] = copy.deepcopy(shots[at:])
    dur = int(clip.get("durationSec") or 8)
    left_dur = max(4, int(round(dur * at / len(shots))))
    right_dur = max(4, dur - left_dur)
    if left_dur + right_dur > 15:
        right_dur = max(4, 15 - left_dur)
    left["durationSec"] = min(15, left_dur)
    right["durationSec"] = min(15, right_dur)
    left["title"] = (clip.get("title") or "Clip") + " A"
    right["title"] = (clip.get("title") or "Clip") + " B"
    apply_fix(left, "reflow")
    apply_fix(right, "reflow")
    right.setdefault("headers", {})["handoffFrom"] = left["id"]
    left.setdefault("headers", {})["next"] = right["id"]
    return left, right


def merge_clips(a: dict, b: dict) -> dict:
    merged = duplicate_clip(a)
    extra = copy.deepcopy(b.get("shots") or [])
    id_map = {}
    for sub in b.get("subjects") or []:
        if not any(s.get("name") == sub.get("name") and s.get("imageFile") == sub.get("imageFile") for s in merged["subjects"]):
            copied = copy.deepcopy(sub)
            new_id = "s" + _token()
            id_map[sub.get("id")] = new_id
            copied["id"] = new_id
            merged["subjects"].append(copied)
        else:
            match = next(s for s in merged["subjects"] if s.get("name") == sub.get("name"))
            id_map[sub.get("id")] = match["id"]
    for shot in extra:
        for line in shot.get("lines") or []:
            line["subjectId"] = id_map.get(line.get("subjectId"), line.get("subjectId"))
        merged["shots"].append(shot)
    merged["durationSec"] = min(15, int(a.get("durationSec") or 0) + int(b.get("durationSec") or 0))
    merged["title"] = (a.get("title") or "Clip") + " + " + (b.get("title") or "")
    apply_fix(merged, "reflow")
    return merged


def link_neighbors(clips: list[dict]) -> None:
    ordered = [c for c in clips if not c.get("variantOf")]
    for i, clip in enumerate(ordered):
        headers = clip.setdefault("headers", {})
        headers["handoffFrom"] = ordered[i - 1]["id"] if i else headers.get("handoffFrom") or ""
        headers["next"] = ordered[i + 1]["id"] if i + 1 < len(ordered) else headers.get("next") or ""
        if i:
            prev = ordered[i - 1]
            if prev.get("renderPath") and not headers.get("endFrame"):
                headers["endFrame"] = prev.get("renderPath") or ""
            if prev.get("facts") and not clip.get("carried"):
                clip["carried"] = prev.get("facts") or prev.get("endState") or ""


def continuity_findings(clips: list[dict]) -> dict:
    ordered = [c for c in clips if not c.get("variantOf")]
    out = {c.get("id"): [] for c in ordered}
    for i, clip in enumerate(ordered):
        if not i:
            continue
        prev = ordered[i - 1]
        facts = [ln.strip() for ln in (prev.get("facts") or "").splitlines() if ln.strip()]
        blob = json.dumps(clip, ensure_ascii=False).lower()
        for fact in facts:
            if fact.lower() not in blob:
                out[clip.get("id")].append({
                    "id": "carry",
                    "severity": "warn",
                    "message": f"Previous clip fact is missing here: {fact}",
                    "focus": "sec-continuity",
                })
        direction = prev.get("screenDirection") or ""
        if direction and clip.get("screenDirection") and clip.get("screenDirection") != direction:
            out[clip.get("id")].append({
                "id": "axis",
                "severity": "warn",
                "message": "Screen direction reverses from the previous clip without a cutaway.",
                "focus": "sec-continuity",
            })
    return out


def apply_template(clip: dict, name: str) -> dict:
    prepare_clip(clip)
    dur = int(clip.get("durationSec") or 8)
    who = (clip.get("subjects") or [{}])[0].get("id", "")

    def shot(size, angle, move, text, start=None):
        return {
            "size": size, "angle": angle, "lens": "85mm" if size in ("close-up", "medium close-up") else ("50mm" if size == "medium" else ""),
            "cameraMove": move, "cameraKey": "", "startSec": start, "text": text, "custom": False,
            "offscreenGuard": size in WIDE, "lines": [], "expression": "", "eyeline": "",
            "onScreenText": "", "onScreenReadable": True, "diegetic": "", "beat": "", "folded": False,
            "visible": [], "moveParts": {"verb": "hold", "amplitude": "", "speed": "", "landing": ""},
        }

    if name == "reverse":
        clip["shots"] = [
            shot("medium close-up", "front", "holds a static shot", "Over the shoulder, the speaker faces frame-left, off the lens."),
            shot("medium close-up", "front", "holds a static shot", "The reverse angle, the listener now speaking, eyes frame-right, off the lens.", round(dur / 2, 3)),
        ]
        clip["shots"][0]["lines"] = [{"subjectId": who, "language": "English", "native": "", "delivery": "", "closeMouth": True, "continuation": "", "voiceover": False}]
    elif name == "escort":
        clip["shots"] = [
            shot("wide", "behind", "tracks from behind at slow speed, keeping a steady distance", "Both figures walk away, faces not visible."),
            shot("medium", "front", "tracks from the front at slow speed, keeping a steady distance", "They walk toward camera and stop in a clear medium framing.", round(dur * 0.45, 3)),
        ]
    elif name == "door":
        clip["shots"] = [shot("medium", "front", "holds a static shot", "At the door, seen from inside the room. The door opens and the person comes through to a medium framing.")]
    elif name == "reaction":
        clip["shots"] = [
            shot("medium close-up", "front", "holds a static shot", "The speaker, front-facing."),
            shot("close-up", "three-quarter", "pushes in with small amplitude at slow speed toward the face", "The listener's reaction.", round(dur * 0.6, 3)),
        ]
    elif name == "montage":
        count = 5
        clip["durationSec"] = max(dur, 10)
        step = clip["durationSec"] / count
        texts = [
            "A full-length view, one figure only.",
            "A three-quarter turn, still one figure.",
            "A clean side profile.",
            "The back view.",
            "A closer waist-up view.",
        ]
        sizes = ["wide", "medium-wide", "medium", "wide", "medium close-up"]
        angles = ["front", "three-quarter", "side", "behind", "front"]
        clip["shots"] = []
        clip["clipKind"] = "sampler"
        for i in range(count):
            clip["shots"].append(shot(sizes[i], angles[i], "holds a static shot", texts[i], None if i == 0 else round(step * i, 3)))
    else:
        clip["shots"] = [shot("medium close-up", "front", "holds a static shot", "")]
        clip["shots"][0]["lines"] = [{"subjectId": who, "language": "English", "native": "", "delivery": "", "closeMouth": True, "continuation": "", "voiceover": False}]
    return clip


def swap_picture(clip: dict, label: int, direction: int) -> dict:
    labels = []
    for sub in clip.get("subjects") or []:
        if sub.get("imageLabel") is not None:
            labels.append(int(sub["imageLabel"]))
    for extra in clip.get("extras") or []:
        if extra.get("label") is not None:
            labels.append(int(extra["label"]))
    ordered = sorted(set(labels))
    if label not in ordered:
        return clip
    idx = ordered.index(label)
    j = idx + direction
    if j < 0 or j >= len(ordered):
        return clip
    other = ordered[j]
    _relabel(clip, label, -1)
    _relabel(clip, other, label)
    _relabel(clip, -1, other)
    return clip


def _relabel(clip: dict, old: int, new: int) -> None:
    token_old = f"<Picture {old}>"
    token_new = f"<Picture {new}>"

    def text(value):
        if isinstance(value, str):
            return value.replace(token_old, token_new)
        if isinstance(value, list):
            return [text(v) for v in value]
        if isinstance(value, dict):
            return {k: text(v) for k, v in value.items()}
        return value

    for sub in clip.get("subjects") or []:
        if sub.get("imageLabel") == old:
            sub["imageLabel"] = new
        sub["description"] = text(sub.get("description") or "")
    for extra in clip.get("extras") or []:
        if extra.get("label") == old:
            extra["label"] = new
        extra["description"] = text(extra.get("description") or "")
    for anchor in clip.get("anchors") or []:
        if anchor.get("imageLabel") == old:
            anchor["imageLabel"] = new
        anchor["note"] = text(anchor.get("note") or "")
    for shot in clip.get("shots") or []:
        shot["text"] = text(shot.get("text") or "")
        shot["cameraMove"] = text(shot.get("cameraMove") or "")
    clip["summary"] = text(clip.get("summary") or "")
    clip["styleOpening"] = text(clip.get("styleOpening") or "")
    clip["notes"] = text(clip.get("notes") or "")
    for row in clip.get("retention") or []:
        row["label"] = text(row.get("label") or "")
        row["note"] = text(row.get("note") or "")
        row["context"] = text(row.get("context") or "")


def api_payload(clip: dict, body: str) -> dict:
    model = "MiniMax-H3-Max" if clip.get("model") == "H3-Max" else "MiniMax-H3"
    files = []
    mode = clip.get("mode")
    frames = clip.get("frames") or {}
    if mode == "i2va":
        files.append({"role": "first_frame", "path": frames.get("first") or ""})
    elif mode == "l2va":
        files.append({"role": "last_frame", "path": frames.get("last") or ""})
    elif mode == "fl2va":
        files.append({"role": "first_frame", "path": frames.get("first") or ""})
        files.append({"role": "last_frame", "path": frames.get("last") or ""})
    else:
        for sub in clip.get("subjects") or []:
            if sub.get("imageFile"):
                files.append({"role": "reference_image", "path": sub.get("imageFile"), "label": f"Picture {sub.get('imageLabel')}"})
        for extra in clip.get("extras") or []:
            files.append({"role": "reference_image", "path": extra.get("file") or "", "label": f"Picture {extra.get('label')}"})
        for video in clip.get("videos") or []:
            files.append({"role": "reference_video", "path": video.get("file") or "", "label": f"Video {video.get('label')}"})
        for sub in clip.get("subjects") or []:
            if sub.get("speaks") and sub.get("timbre") == "audio" and sub.get("audioFile"):
                files.append({"role": "reference_audio", "path": sub.get("audioFile"), "label": f"Audio {sub.get('audioLabel')}"})
    voices = []
    for sub in clip.get("subjects") or []:
        if sub.get("speaks") or any(ln.get("subjectId") == sub.get("id") for s in clip.get("shots") or [] for ln in s.get("lines") or []):
            voices.append({"name": sub.get("name") or "", "voiceId": sub.get("voiceId") or "", "timbre": sub.get("timbre") or ""})
    return {
        "model": model,
        "duration": clip.get("durationSec"),
        "resolution": clip.get("resolution"),
        "ratio": clip.get("ratio"),
        "prompt": body.strip(),
        "files": files,
        "voices": voices,
    }


def plates_header(clips: list[dict], scene_comment: str = "") -> str:
    lines = ["# Attachment order. Written by h3-mechanic."]
    if scene_comment.strip():
        lines.extend(scene_comment.strip().splitlines())
    return "\n".join(lines)


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()[:64]
    except OSError:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        return width, height
    if data[:2] == b"\xff\xd8":
        return _jpeg_size(path)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return _webp_size(path)
    return None


def _jpeg_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height = int.from_bytes(data[i + 5:i + 7], "big")
            width = int.from_bytes(data[i + 7:i + 9], "big")
            return width, height
        if i + 4 > len(data):
            break
        size = int.from_bytes(data[i + 2:i + 4], "big")
        i += 2 + size
    return None


def _webp_size(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:40]
    if data[12:16] == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if data[12:16] == b"VP8 " and len(data) >= 30:
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        return width, height
    return None


def probe(path: str) -> dict:
    target = Path(path).expanduser()
    info = {"path": str(target), "exists": target.is_file(), "width": None, "height": None, "duration": None, "mtime": None}
    if not target.is_file():
        return info
    stat = target.stat()
    info["mtime"] = stat.st_mtime
    info["bytes"] = stat.st_size
    size = image_size(target)
    if size:
        info["width"], info["height"] = size
        if size[0] and size[1]:
            info["aspect"] = round(size[0] / size[1], 4)
    ffprobe = shutil.which("ffprobe")
    if ffprobe and target.suffix.lower() in {".mp4", ".mov", ".webm", ".wav", ".mp3", ".m4a", ".flac"}:
        try:
            proc = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(target)],
                capture_output=True, text=True, timeout=8,
            )
            if proc.stdout.strip():
                info["duration"] = round(float(proc.stdout.strip()), 3)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return info


def file_findings(info: dict, role: str) -> list[dict]:
    if not info.get("exists"):
        if info.get("path"):
            return [_finding("disk", "warn", f"{role} is not on disk: {info.get('path')}", "sec-cast")]
        return []
    out = []
    width, height = info.get("width"), info.get("height")
    if width and height:
        if width < 256 or height < 256 or width > 5760 or height > 5760:
            out.append(_finding("px", "error", f"{role} is {width}×{height}. Each side must be 256–5760.", "sec-cast"))
        aspect = width / height
        if aspect < 0.4 or aspect > 2.5:
            out.append(_finding("px", "error", f"{role} aspect {aspect:.2f} is outside 0.4–2.5.", "sec-cast"))
    duration = info.get("duration")
    if duration is not None and (duration < 2 or duration > 15):
        out.append(_finding("media", "error", f"{role} is {duration:.1f}s. A reference clip must be 2–15 s.", "sec-cast"))
    return out


def safe_home(path: str) -> Path:
    target = Path(path).expanduser().resolve()
    home = Path.home().resolve()
    if target != home and home not in target.parents:
        raise RuntimeError("That path is outside the home directory.")
    return target


def save_media(name: str, data_b64: str) -> str:
    raw = base64.b64decode(data_b64)
    if len(raw) > 40_000_000:
        raise RuntimeError("That file is over 40 MB.")
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", Path(name).name) or "upload.bin"
    MEDIA.mkdir(parents=True, exist_ok=True)
    target = MEDIA / f"{_token()}-{safe}"
    target.write_bytes(raw)
    return str(target)


def list_sheets() -> list[str]:
    return sorted(p.name for p in CHEATSHEETS.glob("*.md"))


def read_sheet(name: str) -> str:
    target = (CHEATSHEETS / Path(name).name).resolve()
    if target.parent != CHEATSHEETS.resolve() or target.suffix != ".md" or not target.is_file():
        raise RuntimeError("Unknown sheet.")
    return target.read_text(encoding="utf-8")


def save_style(style_id: str, opening: str, notes: str) -> str:
    if style_id in {"80s-bollywood", "cinematic-modern", "modern-series", "noir-thriller", "generic"}:
        raise RuntimeError("That style already ships with the editor.")
    if not re.fullmatch(r"[a-z0-9-]{1,40}", style_id):
        raise RuntimeError("Use a short lowercase id, letters, numbers, and hyphens.")
    path = ROOT / "meta-prompts" / "styles" / f"{style_id}.md"
    path.write_text(
        f"# H3 style — {style_id}\n\n{notes.strip()}\n\nOpening: `{opening.strip()}`\n",
        encoding="utf-8",
    )
    extra = []
    if STYLES_EXTRA.is_file():
        extra = json.loads(STYLES_EXTRA.read_text(encoding="utf-8"))
    extra = [row for row in extra if row.get("id") != style_id]
    extra.append({"id": style_id, "opening": opening.strip()})
    STYLES_EXTRA.write_text(json.dumps(extra, indent=2) + "\n", encoding="utf-8")
    return str(path)


def extra_styles() -> list[dict]:
    if not STYLES_EXTRA.is_file():
        return []
    try:
        return json.loads(STYLES_EXTRA.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def episode(clips: list[dict]) -> dict:
    rows = []
    total = 0
    for i, clip in enumerate(clips, start=1):
        if clip.get("variantOf"):
            continue
        dur = int(clip.get("durationSec") or 0)
        total += dur
        speakers = []
        for shot in clip.get("shots") or []:
            for line in shot.get("lines") or []:
                if line.get("native"):
                    speakers.append(line.get("native"))
        rows.append({
            "n": i,
            "id": clip.get("id"),
            "title": clip.get("title") or "",
            "mode": clip.get("mode"),
            "duration": dur,
            "status": clip.get("status") or "draft",
            "lines": len(speakers),
        })
    return {"rows": rows, "total": total}


def _token() -> str:
    import random
    return f"{random.randrange(16**8):08x}"


_SIZE_PHRASES = (
    ("extreme wide", "an extreme wide shot"),
    ("establishing", "an establishing shot"),
    ("medium close-up", "a medium close-up"),
    ("medium-wide", "a medium-wide shot"),
    ("close-up", "a close-up"),
    ("medium", "a medium shot"),
    ("wide", "a wide shot"),
)
_ANGLE_PHRASES = (
    ("three-quarter", "in a three-quarter view"),
    ("overhead", "in an overhead shot"),
    ("front", "front-facing"),
    ("side", "in side profile"),
    ("behind", "from behind"),
    ("low", "in a low angle"),
    ("high", "in a high angle"),
)
_EYES = (
    "Eyes stay toward frame-left, off the lens.",
    "Eyes stay toward frame-right, off the lens.",
    "Eyes stay on the lens.",
    "Eyes stay on the other person, off the lens.",
)


def parse_shot_fields(body: str) -> dict:
    """Pull size, angle, lens, move, and action back out of a rendered shot."""
    work = (body or "").strip()
    work = re.sub(r"^(?:Live-action, cinematic,\s*)+", "", work)
    anchors = []
    while work:
        matched = False
        for pattern, kind in (
            (r"The shot begins from <Picture (\d+)>\.\s*", "composition"),
            (r"the shot's keyframe corresponds to <Picture (\d+)>\.\s*", "keyframe"),
            (r"the shot ends on <Picture (\d+)>\.\s*", "end"),
        ):
            found = re.match(pattern, work, re.I)
            if found:
                anchors.append({"imageLabel": int(found.group(1)), "kind": kind})
                work = work[found.end():]
                matched = True
                break
        if not matched:
            break
    shot = {
        "size": "medium close-up",
        "angle": "front",
        "lens": "",
        "cameraMove": "",
        "offscreenGuard": False,
        "eyeline": "",
        "onScreenText": "",
        "onScreenReadable": True,
        "custom": True,
        "anchors": anchors,
    }
    recognized = False
    for key, phrase in _SIZE_PHRASES:
        for form in (phrase, phrase[:1].upper() + phrase[1:]):
            if work.startswith(form):
                shot["size"] = key
                work = work[len(form):].lstrip(" ,")
                recognized = True
                break
        if recognized:
            break
    for key, phrase in _ANGLE_PHRASES:
        if work.lower().startswith(phrase):
            shot["angle"] = key
            work = work[len(phrase):].lstrip(" ,")
            break
    lens = re.match(r"shot on an? (\d+mm) lens\.?\s*", work, re.I)
    if lens:
        shot["lens"] = lens.group(1)
        work = work[lens.end():]
    if "No other person appears in the frame." in work:
        shot["offscreenGuard"] = True
        work = work.replace("No other person appears in the frame.", "")
    sign = re.search(r'A sign reads "([^"]*)"\.', work)
    if sign:
        shot["onScreenText"] = sign.group(1)
        shot["onScreenReadable"] = True
        work = work.replace(sign.group(0), "")
    if "A sign is visible, its lettering not readable." in work:
        shot["onScreenReadable"] = False
        work = work.replace("A sign is visible, its lettering not readable.", "")
    for eye in _EYES:
        if eye in work:
            shot["eyeline"] = eye[:-1]
            work = work.replace(eye, "")
    move = re.search(r"The camera ([^.]+)\.", work)
    if move:
        shot["cameraMove"] = move.group(1).strip()
        work = work.replace(move.group(0), "")
    shot["custom"] = not recognized
    shot["text"] = re.sub(r"\s+", " ", work).strip(" .")
    return shot


def extract_lines(body: str, subjects: list) -> list:
    lines = []
    pattern = re.compile(
        r"(?:<Subject (\d+)>|([^.]*?)) \(S\d+\) says (in an off-screen voiceover,\s*)?.*?"
        r"<d>\[([^\]]+)\]\s*(.*?)</d>(<scenetrans>|<cutoff>)?",
        re.S,
    )
    for match in pattern.finditer(body or ""):
        subject_id = ""
        if match.group(1) and subjects:
            index = int(match.group(1)) - 1
            if 0 <= index < len(subjects):
                subject_id = subjects[index].get("id") or ""
        elif subjects:
            subject_id = subjects[0].get("id") or ""
        lines.append({
            "subjectId": subject_id,
            "language": match.group(4).strip(),
            "native": match.group(5).strip(),
            "delivery": "",
            "closeMouth": "lips remain completely closed" not in (body or "") and "closes " in (body or ""),
            "voiceover": bool(match.group(3)),
            "continuation": "scenetrans" if match.group(6) == "<scenetrans>" else ("cutoff" if match.group(6) == "<cutoff>" else ""),
            "locked": False,
        })
    return lines


def parse_definitions(text: str) -> tuple[list, list, list]:
    """Subject rows, extra pictures, anchors from a subject_definitions block."""
    subjects, extras, anchors = [], [], []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        subject = re.match(r"<Subject (\d+)> is (.+)\.$", line)
        if subject:
            desc = subject.group(2).strip()
            identity = "supplies identity only" in desc
            desc = re.sub(r"\s*<Picture \d+> supplies identity only.*$", "", desc).strip()
            name_match = re.match(r"the (.+?) in <Picture \d+>", desc, re.I)
            picture = re.search(r"<Picture (\d+)>", desc)
            subjects.append({
                "number": int(subject.group(1)),
                "name": ("the " + name_match.group(1)) if name_match else f"subject {subject.group(1)}",
                "description": desc,
                "imageLabel": int(picture.group(1)) if picture else int(subject.group(1)),
                "identityOnly": identity,
            })
            continue
        anchor = re.match(
            r"<Picture (\d+)> is the (composition anchor|keyframe anchor|end frame) for \[Shot (\d+)\], (.+)\.$",
            line,
        )
        if anchor:
            kind = {"composition anchor": "composition", "keyframe anchor": "keyframe", "end frame": "end"}[anchor.group(2)]
            anchors.append({
                "imageLabel": int(anchor.group(1)),
                "shot": int(anchor.group(3)),
                "kind": kind,
                "note": anchor.group(4).strip(),
            })
            continue
        picture = re.match(r"<Picture (\d+)> is (.+)\.$", line)
        if picture:
            extras.append({
                "label": int(picture.group(1)),
                "description": picture.group(2).strip(),
                "file": "",
                "marker": "attribute_transfer",
            })
    return subjects, extras, anchors


def parse_retention(text: str) -> list:
    rows = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        match = re.match(r"(<(?:Subject|Picture|Video|Audio) \d+>)(?: \((.+)\))?: (\S+)(?: - (.*))?$", line)
        if not match:
            continue
        context = match.group(2) or ""
        shots = [int(n) for n in re.findall(r"\[Shot (\d+)\]", context)] if "appears in" in context else []
        rows.append({
            "label": match.group(1),
            "context": "" if "appears in" in context else context,
            "shots": shots,
            "marker": match.group(3),
            "note": (match.group(4) or "").strip(),
        })
    return rows


def draft_sections(current: dict, imported: dict) -> list:
    sections = [
        {"id": "style", "title": "Style opening", "preview": imported.get("styleOpening") or "", "locked": bool(current.get("lockStyle"))},
        {"id": "summary", "title": "Summary", "preview": imported.get("summary") or "", "locked": False},
        {"id": "subjects", "title": "Subject descriptions", "preview": "\n".join(
            (s.get("name") or "") + " — " + (s.get("description") or "")[:160] for s in imported.get("subjects") or []
        ), "locked": False},
        {"id": "retention", "title": "Retention", "preview": "\n".join(
            f"{r.get('label')} {r.get('marker')}" for r in imported.get("retention") or []
        ), "locked": False},
        {"id": "sound", "title": "Sound", "preview": f"{imported.get('audioPolicy')}: {imported.get('soundscape') or 'N/A'}", "locked": False},
        {"id": "anchors", "title": "Anchors", "preview": "\n".join(
            f"Picture {a.get('imageLabel')} shot {a.get('shot')} {a.get('kind')}" for a in imported.get("anchors") or []
        ), "locked": False},
    ]
    current_shots = current.get("shots") or []
    for i, shot in enumerate(imported.get("shots") or []):
        locked = i < len(current_shots) and bool(current_shots[i].get("locked"))
        spoken = " / ".join(ln.get("native") or "" for ln in shot.get("lines") or [])
        sections.append({
            "id": f"shot-{i}",
            "title": f"Shot {i + 1}",
            "preview": ((shot.get("text") or "") + (" · " + spoken if spoken else ""))[:400],
            "locked": locked,
        })
    return [row for row in sections if row["preview"].strip()]


def apply_draft(current: dict, imported: dict, accept: list) -> dict:
    """Copy the chosen sections of a parsed draft onto the open clip."""
    chosen = set(accept or [])
    if not chosen:
        chosen = {row["id"] for row in draft_sections(current, imported) if not row["locked"]}
    prepare_clip(current)
    if "style" in chosen and not current.get("lockStyle"):
        current["styleOpening"] = imported.get("styleOpening") or current.get("styleOpening")
    if "summary" in chosen:
        current["summary"] = imported.get("summary") or ""
        if imported.get("taskTypes"):
            current["taskTypes"] = imported["taskTypes"]
    if "sound" in chosen:
        current["audioPolicy"] = imported.get("audioPolicy") or current.get("audioPolicy")
        current["soundscape"] = imported.get("soundscape") or ""
        current["music"] = imported.get("music") or ""
    if "retention" in chosen:
        current["retention"] = imported.get("retention") or []
    if "subjects" in chosen:
        for i, sub in enumerate(imported.get("subjects") or []):
            if i < len(current.get("subjects") or []):
                cur = current["subjects"][i]
                if cur.get("locked"):
                    continue
                cur["name"] = sub.get("name") or cur.get("name")
                cur["description"] = sub.get("description") or cur.get("description")
                cur["identityOnly"] = bool(sub.get("identityOnly"))
                if not cur.get("imageFile"):
                    cur["imageLabel"] = sub.get("imageLabel") or cur.get("imageLabel")
            else:
                current["subjects"].append(sub)
    if "anchors" in chosen:
        current["anchors"] = imported.get("anchors") or []
    incoming = imported.get("shots") or []
    for i, shot in enumerate(incoming):
        if f"shot-{i}" not in chosen:
            continue
        if i < len(current.get("shots") or []) and current["shots"][i].get("locked"):
            continue
        old_lines = current["shots"][i].get("lines") if i < len(current.get("shots") or []) else []
        for n, line in enumerate(shot.get("lines") or []):
            index = 0
            for s_i, sub in enumerate(imported.get("subjects") or []):
                if sub.get("id") == line.get("subjectId"):
                    index = s_i
            if current.get("subjects") and index < len(current["subjects"]):
                line["subjectId"] = current["subjects"][index]["id"]
            if old_lines and n < len(old_lines) and old_lines[n].get("locked"):
                line["native"] = old_lines[n].get("native")
                line["language"] = old_lines[n].get("language")
                line["locked"] = True
        if i < len(current.get("shots") or []):
            current["shots"][i] = shot
        else:
            current["shots"].append(shot)
    for shot in current.get("shots") or []:
        shot.setdefault("moveParts", {"verb": "hold", "amplitude": "", "speed": "", "landing": ""})
    current["aiDraft"] = ""
    return current


def _image_path(value: str) -> str:
    if not value:
        return ""
    if Path(value).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return value
    return ""


def _next_picture(clip: dict) -> int:
    labels = [int(s.get("imageLabel") or 0) for s in clip.get("subjects") or []]
    labels += [int(s.get("label") or 0) for s in clip.get("extras") or []]
    labels += [int(s.get("imageLabel") or 0) for s in clip.get("anchors") or []]
    return max(labels or [0]) + 1


def spawn_next(clips: list, clip_id: str) -> tuple[list, str]:
    """Open the following clip on this clip's end state and end still."""
    index = next(i for i, clip in enumerate(clips) if clip.get("id") == clip_id)
    current = clips[index]
    same = (
        index + 1 < len(clips)
        and not clips[index + 1].get("variantOf")
        and (clips[index + 1].get("sceneId") or "") == (current.get("sceneId") or "")
    )
    if same:
        nxt = clips[index + 1]
    else:
        nxt = duplicate_clip(current)
        nxt["title"] = (current.get("title") or "Clip") + " next"
        nxt["summary"] = ""
        nxt["shots"] = [{
            "size": "medium close-up", "angle": "front", "lens": "85mm",
            "cameraMove": "holds a static shot", "cameraKey": "", "startSec": None,
            "text": "", "custom": False, "offscreenGuard": False, "lines": [],
            "expression": "", "eyeline": "", "onScreenText": "", "onScreenReadable": True,
            "diegetic": "", "beat": "", "folded": False, "visible": [], "locked": False,
            "moveParts": {"verb": "hold", "amplitude": "", "speed": "", "landing": ""},
        }]
        nxt["anchors"] = []
        clips.insert(index + 1, nxt)
    end = (current.get("endState") or "").strip()
    if end and nxt.get("shots") and not (nxt["shots"][0].get("text") or "").strip():
        nxt["shots"][0]["text"] = end
    still = _image_path(current.get("endStill") or "") or _image_path((current.get("headers") or {}).get("endFrame") or "") or _image_path(current.get("renderPath") or "")
    if still:
        already = any((a.get("note") or "").startswith("the end still") for a in nxt.get("anchors") or [])
        if not already:
            label = _next_picture(nxt)
            nxt.setdefault("extras", []).append({
                "label": label, "file": still,
                "description": "the end still of the previous clip",
                "marker": "fully_preserved",
            })
            nxt.setdefault("anchors", []).append({
                "imageLabel": label, "shot": 1, "kind": "composition",
                "note": "the end still of the previous clip",
            })
        nxt.setdefault("headers", {})["endFrame"] = still
        current.setdefault("headers", {})["endFrame"] = still
    nxt["carried"] = current.get("facts") or end
    nxt.setdefault("headers", {})["handoffFrom"] = current.get("id")
    current.setdefault("headers", {})["next"] = nxt.get("id")
    if current.get("lightLock"):
        nxt["lightLock"] = True
    if current.get("screenDirection") and not nxt.get("screenDirection"):
        nxt["screenDirection"] = current.get("screenDirection")
    nxt["sceneId"] = current.get("sceneId") or nxt.get("sceneId")
    return clips, nxt.get("id")


def clip_paths(clip: dict) -> list[tuple[str, str]]:
    rows = []
    for sub in clip.get("subjects") or []:
        if sub.get("imageFile"):
            rows.append((sub["imageFile"], f"Picture {sub.get('imageLabel')}"))
        if sub.get("speaks") and sub.get("timbre") == "audio" and sub.get("audioFile"):
            rows.append((sub["audioFile"], f"Audio {sub.get('audioLabel')}"))
    for extra in clip.get("extras") or []:
        if extra.get("file"):
            rows.append((extra["file"], f"Picture {extra.get('label')}"))
    for video in clip.get("videos") or []:
        if video.get("file"):
            rows.append((video["file"], f"Video {video.get('label')}"))
    frames = clip.get("frames") or {}
    if frames.get("first"):
        rows.append((frames["first"], "Opening frame"))
    if frames.get("last"):
        rows.append((frames["last"], "Closing frame"))
    return rows


def clip_file_findings(clip: dict) -> list:
    found = []
    seen = set()
    for path, role in clip_paths(clip):
        if path in seen:
            continue
        seen.add(path)
        found.extend(file_findings(probe(path), role))
    durations = [probe(path).get("duration") for path, role in clip_paths(clip) if role.startswith("Video") or role.startswith("Audio")]
    durations = [d for d in durations if isinstance(d, (int, float))]
    if sum(durations) > 15:
        found.append({
            "id": "media", "severity": "error",
            "message": f"Reference media totals {sum(durations):.1f}s. The limit for each type is 15s.",
            "focus": "sec-cast",
        })
    return found


def self_test() -> None:
    clip = {
        "id": "c1", "mode": "ref2va", "title": "A", "model": "H3", "durationSec": 8,
        "resolution": "768P", "ratio": "adaptive", "audioPolicy": "dialogue-only",
        "style": "cinematic-modern", "styleOpening": "The target video is a test.",
        "subjects": [{"id": "s1", "name": "the woman", "kind": "person", "gender": "female", "speaks": True,
                       "imageLabel": 1, "imageFile": "/tmp/a.png", "timbre": "library", "voiceId": "F3"}],
        "shots": [{
            "size": "medium close-up", "angle": "front", "lens": "85mm",
            "cameraMove": "holds a static shot", "startSec": None, "text": "She waits, mouth closed.",
            "lines": [{"subjectId": "s1", "language": "English", "native": "Wait.", "closeMouth": True, "voiceover": True}],
        }],
        "anchors": [], "extras": [], "videos": [], "taskTypes": ["reference generation"], "summary": "She waits.",
        "autoTasks": True, "clipKind": "narrative",
    }
    prepare_clip(clip)
    phrase = build_move({"verb": "push", "amplitude": "small", "speed": "slow", "landing": "toward her face"})
    assert phrase == "pushes in with small amplitude at slow speed toward her face", phrase
    assert "audio reference" not in auto_task_types(clip)
    clip["anchors"] = [{"imageLabel": 1, "shot": 1, "kind": "end"}]
    assert "keyframe completion" in effective_tasks(clip)
    left, right = split_clip(clip, 1) if len(clip["shots"]) > 1 else (None, None)
    if left is None:
        clip["shots"].append(copy.deepcopy(clip["shots"][0]))
        clip["shots"][1]["startSec"] = 4
        left, right = split_clip(clip, 1)
    assert left["shots"] and right["shots"]
    merged = merge_clips(left, right)
    assert len(merged["shots"]) == len(left["shots"]) + len(right["shots"])
    project = prepare_project({"title": "t", "clips": [clip]})
    assert project["scenes"][0]["clipIds"] == [clip["id"]]
    payload = api_payload(clip, "hello")
    assert payload["files"][0]["role"] == "reference_image"
    assert line_seconds({"language": "English", "native": "one two three four five"}) == 2
    parsed = parse_shot_fields(
        "The shot begins from <Picture 1>. A medium close-up, front-facing, shot on an 85mm lens. "
        "She stands at the rail, mouth closed, eyes on the lens. The camera holds a static shot."
    )
    assert parsed["size"] == "medium close-up" and parsed["lens"] == "85mm", parsed
    assert parsed["cameraMove"] == "holds a static shot"
    assert parsed["custom"] is False
    assert parsed["anchors"][0]["kind"] == "composition"
    missing = clip_file_findings({"subjects": [{"imageFile": "/tmp/does-not-exist-h3m.png", "imageLabel": 1}], "extras": [], "videos": [], "frames": {}})
    assert any(row["id"] == "disk" for row in missing)
    print("ok  studio self-test")
