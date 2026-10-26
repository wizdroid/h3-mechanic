# h3-mechanic

A form for writing MiniMax H3 prompts. It has one tab each for T2VA, I2VA, FL2VA, L2VA and Ref2VA, plus a Settings tab. The page assembles the prompt, checks it against the H3 rules, and can pass it to an AI provider to reformat.

## Requirements

Python 3.11 or newer. No extra packages.

## Run

```bash
python3 app/server.py
```

Open http://127.0.0.1:9013. The server listens on loopback only.

Other commands:

```bash
python3 app/server.py --self-test
python3 app/rules_build.py
```

The second command rebuilds `rules/rules.json` from the workbook in `cheatsheets/`.

## Usage

- Pick a mode tab and add a clip. Drag clips and shots to reorder them.
- Ref2VA clips take subjects, extra pictures, composition anchors, timbre, summary task types, retention, shots and dialogue.
- Frame modes take one opening frame, one closing frame, or both. People in those clips do not get a separate character image.
- The right column shows the prompt, the 7000 character counter, the checks and the attach order. A missing file is marked MISSING.
- Copy takes the prompt body. Download and Export scene write `clip-01-8s.txt`, and Export also writes `PLATES.txt`. Header lines (`handoff-from`, `end-frame`, `next`) stay in the file and off the clipboard.
- Save downloads a `.h3m.json` project. The browser also keeps the project locally.

## Settings

Theme, accent, font scale and native-script font are set here, along with the AI providers: DeepSeek, Claude, Google AI, an OpenAI-compatible host, and Ollama. Keys are stored in `~/.config/h3-mechanic/secrets.json` and never in the repository. Offline mode turns the AI buttons off. Assembly and checks keep working.

## Layout

| Path | Contents |
| --- | --- |
| `app/` | Server, engine and static front end |
| `cheatsheets/` | H3 reference sheets and the source workbook |
| `meta-prompts/` | Instructions used by the AI actions |
| `rules/` | Menu wording and limits, built from the workbook |

## Theme

The interface uses the shared `wiz-theme.css` stylesheet. Themes are light, dark, nord and nord-light, with blue, pink, green and purple accents.
