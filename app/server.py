"""Local editor server for h3-mechanic. Loopback only.

    python3 app/server.py
    python3 app/server.py --self-test
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP = Path(__file__).resolve().parent
ROOT = APP.parent
sys.path.insert(0, str(APP))

import engine  # noqa: E402
import studio  # noqa: E402

STATIC = APP / "static"
THEME = Path("/home/wizdroid/Applications/themes/wiz-theme.css")
META = ROOT / "meta-prompts"
SECRETS = Path.home() / ".config" / "h3-mechanic" / "secrets.json"
HOST = "127.0.0.1"
PORT = 9013

BANK = engine.banks()


def _read_json(handler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    data = json.loads(raw.decode("utf-8") or "{}")
    return data if isinstance(data, dict) else {}


def _secrets() -> dict:
    if not SECRETS.is_file():
        return {}
    try:
        return json.loads(SECRETS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_secrets(data: dict) -> None:
    SECRETS.parent.mkdir(parents=True, exist_ok=True)
    SECRETS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(SECRETS, 0o600)


def _key(provider: str) -> str:
    env = {
        "deepseek": "DEEPSEEK_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
    }.get(provider, "")
    saved = (_secrets().get(provider) or "").strip()
    if saved:
        return saved
    return os.environ.get(env, "").strip() if env else ""


def _http_json(url: str, payload: dict | None, headers: dict, timeout: int = 40) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="GET" if payload is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach the provider: {exc.reason}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The provider did not return JSON.") from exc


def _meta(mode: str, style: str) -> str:
    chunks = []
    for path in (
        META / "shared-rules.md",
        META / ("ref2va.md" if mode == "ref2va" else "t2va.md" if mode == "t2va" else "i2va-fl2va-l2va.md"),
        META / "styles" / f"{style}.md" if style and style != "generic" else None,
    ):
        if path and path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def _extract_text(reply: str) -> str:
    fence = re.search(r"```(?:text)?\s*\n(.*?)```", reply, re.S)
    return (fence.group(1) if fence else reply).strip()


def chat(provider: str, cfg: dict, system: str, user: str) -> str:
    base = (cfg.get("baseUrl") or "").rstrip("/")
    model = (cfg.get("model") or "").strip()
    if provider == "ollama":
        if not model:
            raise RuntimeError("Pick an Ollama model.")
        data = _http_json(base + "/api/chat", {
            "model": model, "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }, {"Content-Type": "application/json"})
        return ((data.get("message") or {}).get("content") or "").strip()
    if provider == "claude":
        key = _key("claude")
        if not key:
            raise RuntimeError("Claude has no API key.")
        data = _http_json(base + "/v1/messages", {
            "model": model or "claude-sonnet-4-5",
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }, {
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        })
        parts = data.get("content") or []
        return "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    if provider == "gemini":
        key = _key("gemini")
        if not key:
            raise RuntimeError("Google AI has no API key.")
        model = model or "gemini-2.5-flash"
        data = _http_json(
            f"{base}/models/{model}:generateContent?key={key}",
            {"contents": [{"parts": [{"text": system + "\n\n" + user}]}]},
            {"Content-Type": "application/json"},
        )
        cands = data.get("candidates") or []
        parts = (((cands[0] if cands else {}).get("content") or {}).get("parts") or [])
        return "\n".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    # DeepSeek and any OpenAI-compatible host.
    key = _key(provider)
    if provider != "ollama" and not key and provider != "openai":
        raise RuntimeError(f"{provider} has no API key.")
    if provider == "openai" and not key:
        raise RuntimeError("The OpenAI-compatible provider has no API key.")
    url = base + ("" if base.endswith("/chat/completions") else "/chat/completions")
    if provider == "deepseek" and not base.endswith("/chat/completions"):
        url = base + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = _http_json(url, {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }, headers)
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("The provider returned no choices.")
    return ((choices[0].get("message") or {}).get("content") or "").strip()


def list_models(provider: str, cfg: dict) -> list[str]:
    base = (cfg.get("baseUrl") or "").rstrip("/")
    if provider == "ollama":
        data = _http_json(base + "/api/tags", None, {})
        return [m.get("name") for m in data.get("models") or [] if m.get("name")]
    if provider == "gemini":
        key = _key("gemini")
        if not key:
            raise RuntimeError("Google AI has no API key.")
        data = _http_json(base + "/models?key=" + key, None, {})
        names = []
        for m in data.get("models") or []:
            name = (m.get("name") or "").replace("models/", "")
            if "generateContent" in (m.get("supportedGenerationMethods") or ["generateContent"]):
                names.append(name)
        return names
    key = _key(provider)
    url = base + ("" if base.endswith("/models") else "/models")
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = _http_json(url, None, headers)
    return [m.get("id") for m in data.get("data") or [] if m.get("id")]


def probe_ollama(hosts: list[str]) -> dict:
    tried = []
    for host in hosts:
        host = host.rstrip("/")
        tried.append(host)
        try:
            models = list_models("ollama", {"baseUrl": host})
            return {"ok": True, "baseUrl": host, "models": models}
        except RuntimeError:
            continue
    return {"ok": False, "tried": tried, "models": []}


IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MEDIA_EXT = IMAGE_EXT | {".mp4", ".mov", ".webm", ".wav", ".mp3", ".flac", ".m4a", ".txt", ".json"}


def browse(path: str) -> dict:
    raw = Path(path or Path.home()).expanduser()
    try:
        folder = raw.resolve()
    except OSError as exc:
        raise RuntimeError(str(exc)) from exc
    if not folder.is_dir():
        raise RuntimeError("Not a folder.")
    dirs, files = [], []
    try:
        children = sorted(folder.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        raise RuntimeError(str(exc)) from exc
    for child in children:
        if child.name.startswith("."):
            continue
        if child.is_dir():
            dirs.append(child.name)
        elif child.suffix.lower() in MEDIA_EXT:
            files.append(child.name)
        if len(dirs) + len(files) >= 400:
            break
    parent = str(folder.parent) if folder.parent != folder else str(folder)
    return {"path": str(folder), "parent": parent, "dirs": dirs[:200], "files": files[:200]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

    def _file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._json(404, {"error": "Not found."})
            return
        self._send(200, path.read_bytes(), content_type)

    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        path = url.path
        if path in ("/", "/index.html"):
            self._file(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.js":
            self._file(STATIC / "app.js", "text/javascript; charset=utf-8")
            return
        if path == "/studio.js":
            self._file(STATIC / "studio.js", "text/javascript; charset=utf-8")
            return
        if path == "/app.css":
            self._file(STATIC / "app.css", "text/css; charset=utf-8")
            return
        if path == "/themes/wiz-theme.css":
            self._file(THEME, "text/css; charset=utf-8")
            return
        if path == "/api/banks":
            self._json(200, {"banks": BANK, "project": engine.new_project()})
            return
        if path == "/api/secrets":
            have = {name: bool((value or "").strip()) for name, value in _secrets().items()}
            for name, env in (
                ("deepseek", "DEEPSEEK_API_KEY"),
                ("claude", "ANTHROPIC_API_KEY"),
                ("gemini", "GEMINI_API_KEY"),
                ("openai", "OPENAI_API_KEY"),
            ):
                have[name] = have.get(name, False) or bool(os.environ.get(env))
            self._json(200, {"keys": have})
            return
        if path == "/api/sheets":
            qs = parse_qs(url.query)
            name = (qs.get("name") or [""])[0]
            if not name:
                self._json(200, {"sheets": studio.list_sheets()})
                return
            self._json(200, {"name": name, "text": studio.read_sheet(name)})
            return
        if path == "/api/thumb":
            qs = parse_qs(url.query)
            try:
                target = studio.safe_home((qs.get("path") or [""])[0])
            except RuntimeError as exc:
                self._json(400, {"error": str(exc)})
                return
            if target.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"} or not target.is_file():
                self._json(404, {"error": "Not an image."})
                return
            kind = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
            self._file(target, kind[target.suffix.lower()])
            return
        if path == "/api/browse":
            qs = parse_qs(url.query)
            try:
                self._json(200, browse((qs.get("path") or [""])[0]))
            except RuntimeError as exc:
                self._json(400, {"error": str(exc)})
            return
        self._json(404, {"error": "Not found."})

    def do_POST(self):  # noqa: N802
        url = urlparse(self.path)
        try:
            data = _read_json(self)
        except json.JSONDecodeError:
            self._json(400, {"error": "The body is not JSON."})
            return
        try:
            self._post(url.path, data)
        except RuntimeError as exc:
            self._json(400, {"error": str(exc)})
        except OSError as exc:
            self._json(400, {"error": str(exc)})

    def _post(self, path: str, data: dict) -> None:
        if path == "/api/assemble":
            clip = data.get("clip") or {}
            self._json(200, engine.assemble(clip, BANK))
            return
        if path == "/api/retention":
            self._json(200, {"retention": engine.sync_retention(data.get("clip") or {})})
            return
        if path == "/api/import/prompt":
            clip = engine.import_prompt(data.get("text") or "", data.get("mode") or "ref2va")
            packed = engine.assemble(clip, BANK)
            packed["clip"] = clip
            self._json(200, packed)
            return
        if path == "/api/import/scene":
            folder = data.get("directory") or ""
            if not folder:
                raise RuntimeError("Name a scene folder.")
            clips = engine.import_scene(folder)
            if not clips:
                raise RuntimeError("That folder has no clip-*.txt files.")
            self._json(200, {"clips": clips})
            return
        if path == "/api/export":
            directory = data.get("directory") or ""
            clips = data.get("clips") or []
            if not directory:
                raise RuntimeError("Name a folder to export into.")
            if not clips:
                raise RuntimeError("There are no clips to export.")
            out = Path(directory).expanduser()
            out.mkdir(parents=True, exist_ok=True)
            written = []
            skipped = []
            force = bool(data.get("force"))
            for i, clip in enumerate(clips, start=1):
                packed = engine.assemble(clip, BANK)
                errors = [f for f in packed["findings"] if f.get("severity") == "error"]
                if errors and not force:
                    skipped.append(f"{clip.get('title') or 'clip'} ({errors[0]['id']}): {errors[0]['message']}")
                    continue
                name = engine.clip_filename(clip, i)
                target = out / name
                target.write_text(engine.file_text(clip, packed["text"]), encoding="utf-8")
                written.append(str(target))
            plates = out / "PLATES.txt"
            plates.write_text(engine.plates_text(clips), encoding="utf-8")
            written.append(str(plates))
            self._json(200, {"written": written, "skipped": skipped})
            return
        if path == "/api/save":
            directory = data.get("path") or ""
            project = data.get("project")
            if not directory or project is None:
                raise RuntimeError("Name a file path and include the project.")
            target = Path(directory).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")
            self._json(200, {"path": str(target)})
            return
        if path == "/api/secrets":
            provider = data.get("provider") or ""
            if provider not in ("deepseek", "claude", "gemini", "openai"):
                raise RuntimeError("Unknown provider.")
            saved = _secrets()
            value = data.get("key")
            if value:
                saved[provider] = str(value).strip()
            elif provider in saved:
                del saved[provider]
            _write_secrets(saved)
            self._json(200, {"ok": True, "set": bool(saved.get(provider))})
            return
        if path == "/api/provider/test":
            self._provider_test(data)
            return
        if path == "/api/provider/models":
            provider = data.get("provider") or "ollama"
            if provider == "ollama" and data.get("detect"):
                hosts = [data.get("baseUrl") or "http://127.0.0.1:11434", "http://127.0.0.1:11434", "http://localhost:11434"]
                self._json(200, probe_ollama(hosts))
                return
            models = list_models(provider, {"baseUrl": data.get("baseUrl") or ""})
            self._json(200, {"ok": True, "models": models})
            return
        if path == "/api/ai":
            self._ai(data)
            return
        if path == "/api/studio":
            self._studio(data)
            return
        self._json(404, {"error": "Not found."})

    def _studio(self, data: dict) -> None:
        global BANK
        action = data.get("action") or ""
        clip = data.get("clip") or {}
        if action == "fix":
            fixed = studio.apply_fix(clip, data.get("fix") or "")
            self._json(200, {"clip": fixed, **engine.assemble(fixed, BANK)})
            return
        if action == "probe":
            info = studio.probe(data.get("path") or "")
            info["findings"] = studio.file_findings(info, data.get("role") or "File")
            self._json(200, info)
            return
        if action == "media":
            path = studio.save_media(data.get("name") or "upload.bin", data.get("data") or "")
            self._json(200, {"path": path})
            return
        if action == "migrate":
            self._json(200, {"project": studio.prepare_project(data.get("project") or {})})
            return
        if action == "continuity":
            clips = data.get("clips") or []
            self._json(200, {"findings": studio.continuity_findings(clips), "episode": studio.episode(clips)})
            return
        if action == "template":
            shaped = studio.apply_template(clip, data.get("name") or "single")
            self._json(200, {"clip": shaped, **engine.assemble(shaped, BANK)})
            return
        if action == "duplicate":
            self._json(200, {"clip": studio.duplicate_clip(clip, bool(data.get("variant")))})
            return
        if action == "split":
            left, right = studio.split_clip(clip, int(data.get("at") or 1))
            self._json(200, {"clips": [left, right]})
            return
        if action == "merge":
            self._json(200, {"clip": studio.merge_clips(data.get("left") or {}, data.get("right") or {})})
            return
        if action == "link":
            clips = data.get("clips") or []
            studio.link_neighbors(clips)
            self._json(200, {"clips": clips})
            return
        if action == "swap":
            swapped = studio.swap_picture(clip, int(data.get("label") or 0), int(data.get("direction") or 0))
            self._json(200, {"clip": swapped, **engine.assemble(swapped, BANK)})
            return
        if action == "move":
            parts = studio.beat_parts(data.get("beat") or "line", (clip.get("style") or "")) if data.get("beat") else (data.get("parts") or {})
            label = ""
            subjects = clip.get("subjects") or []
            if subjects:
                label = f"<Subject 1>"
            phrase = studio.build_move(parts, label)
            self._json(200, {"parts": parts, "phrase": phrase})
            return
        if action == "style":
            path = studio.save_style(data.get("id") or "", data.get("opening") or "", data.get("notes") or "")
            self._json(200, {"path": path, "styles": studio.extra_styles()})
            return
        if action == "rebuild-rules":
            import rules_build
            payload = rules_build.build()
            rules_build.OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            BANK = engine.banks()
            self._json(200, {"ok": True, "rows": sum(len(v) for v in payload["sheets"].values())})
            return
        if action == "diff":
            imported = engine.import_prompt(data.get("draft") or "", (clip.get("mode") or "ref2va"))
            self._json(200, {"sections": studio.draft_sections(clip, imported)})
            return
        if action == "apply-draft":
            imported = engine.import_prompt(data.get("draft") or "", (clip.get("mode") or "ref2va"))
            merged = studio.apply_draft(clip, imported, data.get("accept") or [])
            self._json(200, {"clip": merged, **engine.assemble(merged, BANK)})
            return
        if action == "continue":
            clips = data.get("clips") or []
            clips, new_id = studio.spawn_next(clips, data.get("clipId") or "")
            self._json(200, {"clips": clips, "clipId": new_id})
            return
        if action == "lock":
            target = Path(data.get("path") or "")
            if not target:
                raise RuntimeError("Name the project file.")
            lock = target.with_suffix(target.suffix + ".lock")
            token = data.get("token") or ""
            if lock.is_file() and not data.get("take"):
                current = lock.read_text(encoding="utf-8").strip()
                if current and current != token:
                    self._json(200, {"busy": True, "holder": current[:12]})
                    return
            lock.write_text(token + "\n", encoding="utf-8")
            self._json(200, {"busy": False})
            return
        raise RuntimeError("Unknown studio action.")

    def _provider_test(self, data: dict) -> None:
        provider = data.get("provider") or ""
        cfg = {"baseUrl": data.get("baseUrl") or "", "model": data.get("model") or ""}
        if provider == "ollama":
            found = probe_ollama([cfg["baseUrl"] or "http://127.0.0.1:11434"])
            if not found["ok"]:
                raise RuntimeError("Ollama did not answer on " + ", ".join(found["tried"]) + ".")
            self._json(200, {
                "ok": True,
                "detail": f"{len(found['models'])} models on {found['baseUrl']}",
                "models": found["models"],
                "baseUrl": found["baseUrl"],
            })
            return
        text = chat(provider, cfg, "Reply with the single word ok.", "ping")
        models = []
        try:
            models = list_models(provider, cfg)
        except RuntimeError:
            models = []
        self._json(200, {"ok": True, "detail": (text or "ok")[:80], "models": models})

    def _ai(self, data: dict) -> None:
        if data.get("offline"):
            raise RuntimeError("Offline mode is on. Assembly and checks still work.")
        provider = data.get("provider") or ""
        action = data.get("action") or "reformat"
        clip = data.get("clip") or {}
        mode = clip.get("mode") or "ref2va"
        system = _meta(mode, clip.get("style") or "")
        draft = data.get("draft") or engine.render_clip(clip, BANK)
        if action == "summary":
            user = (
                "Write only the summary paragraph for this MiniMax H3 prompt. "
                "Use labels that already exist. Do not add a section header. "
                "One short paragraph.\n\n" + draft
            )
        elif action == "grammar":
            user = (
                "Fix grammar and wording in this MiniMax H3 prompt. "
                "Keep every label, timestamp, speaker id, and the text inside <d> tags verbatim. "
                "Return the full prompt in one text fence.\n\n" + draft
            )
        else:
            user = (
                "Reformat this draft into a standards-compliant MiniMax H3 "
                f"{mode} prompt. Do not invent new story events. "
                "Return the full prompt in one text fence.\n\n" + draft
            )
        reply = chat(provider, {"baseUrl": data.get("baseUrl") or "", "model": data.get("model") or ""}, system, user)
        text = _extract_text(reply) if action != "summary" else reply.strip()
        if not text:
            raise RuntimeError("The provider returned an empty reply.")
        self._json(200, {"text": text})


def _color_lint() -> None:
    banned = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(|font-family\s*:\s*[\"'](?!var)")
    for name in ("app.css", "index.html"):
        text = (STATIC / name).read_text(encoding="utf-8")
        # font-size: 12px is a scale, allowed. Colors and font-family literals are not.
        hits = []
        for i, line in enumerate(text.splitlines(), start=1):
            if banned.search(line):
                hits.append(f"{name}:{i}: {line.strip()}")
        if hits:
            raise SystemExit("theme lint failed\n" + "\n".join(hits))
    print("ok  theme lint")


def main() -> None:
    if "--self-test" in sys.argv:
        engine.self_test()
        _color_lint()
        # Assemble through the same function the page uses.
        project = engine.new_project()
        for mode in ("t2va", "i2va", "fl2va", "l2va", "ref2va"):
            clip = engine.new_clip(mode)
            if mode == "i2va":
                clip["frames"]["first"] = "/tmp/a.png"
            if mode == "fl2va":
                clip["frames"] = {"first": "/tmp/a.png", "last": "/tmp/b.png"}
            if mode == "l2va":
                clip["frames"]["last"] = "/tmp/b.png"
            packed = engine.assemble(clip, BANK)
            assert packed["text"].strip()
            assert "chars" in packed
        assert project["schemaVersion"] == 2
        assert project["scenes"]
        print("ok  server self-test")
        return
    port = PORT
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    httpd = ThreadingHTTPServer((HOST, port), Handler)
    print(f"h3-mechanic  http://{HOST}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
