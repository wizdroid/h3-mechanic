# h3-mechanic

A form for writing MiniMax H3 prompts. One tab each for **T2VA**, **I2VA**, **FL2VA**, **L2VA**, and **Ref2VA**, plus Settings. The page assembles the prompt, checks it, and can hand it to an AI provider to reformat.

The screen-by-screen spec is [documents/detailed-specification.md](documents/detailed-specification.md). The requirements are [documents/specification.md](documents/specification.md).

## Run

```bash
cd /home/wizdroid/Applications/h3-mechanic
python3 app/server.py
```

Open http://127.0.0.1:9013 . The server listens on loopback. Python 3.11+ from the system, no extra packages.

```bash
python3 app/server.py --self-test
python3 app/rules_build.py          # workbook -> rules/rules.json
```

## What you do in the page

- Pick a mode tab and add a clip. Drag clips and shots to reorder them.
- Ref2VA: subjects, extra pictures (a tattoo or other hidden attribute), composition anchors, timbre (library voice or an audio file), summary task types, retention, shots, dialogue.
- Frame modes: one opening frame, one closing frame, or both. People in those clips do not get a separate character image.
- The right column is the prompt, the 7000-character counter, the checks, and the attach order. A missing file is marked MISSING.
- Copy takes the prompt body. Download and Export scene write `clip-01-8s.txt`. Export also writes `PLATES.txt`. Header lines (`handoff-from`, `end-frame`, `next`) are on the file and stay off the clipboard.
- Save downloads a `.h3m.json` project. The browser also keeps the project locally.
- Settings: theme, accent, font scale, native-script font, and providers (DeepSeek, Claude, Google AI, an OpenAI-compatible host, Ollama). Keys stay in `~/.config/h3-mechanic/secrets.json`. Offline turns the AI buttons off. Assembly and checks keep working.

Wording for the camera, voice, and expression menus comes from `rules/rules.json`, built from `cheatsheets/minimax-h3-cheatsheet-categorized.xlsx`. AI actions read `meta-prompts/`.

Colors come from `/home/wizdroid/Applications/themes/wiz-theme.css`.
