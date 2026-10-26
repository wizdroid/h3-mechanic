# 15 — Troubleshooting

Find the symptom, apply the **prompt fix first**, then the pipeline fix. ComfyUI workflow names refer to the sorted workflows (`minimax/`, `face/`, `upscale/`).

## Faces and identity

| Symptom | Likely cause | Prompt fix | Pipeline fix |
|---|---|---|---|
| Melted or warped faces | Face too small: wide shot, fast motion, edge of frame | Move faces to MCU/MS; wide only from behind; add `shot on an 85mm lens, compressed perspective, natural proportions`; `centered`, `steady distance`; slow speed | Render 2K; `face/reactor-video-faceswap` then a light FaceDetailer pass (denoise 0.2–0.35, fixed seed); `minimax/minimax-h3-face-restore` |
| Faces stretched near edges | Wide-angle wording, subject at the frame edge | Remove `24mm`, `wide-angle`, `fisheye`; center the subject | Crop in the edit |
| Wrong person / new face | Identity not tied to a reference; prompt describes features that fight the image | One identity image per visible person; `fully_preserved`; describe only features the image shows, or use identity-locked phrasing (`with his face, hair, build and complete outfit taken exactly from the reference`) | ReActor swap with the reference face |
| Identity drifts mid-clip | Too many shots, big angle changes, face turns to profile then back | Fewer shots; keep the same angle family; three-quarter instead of full profile | ReActor |
| Costume drifts | Outfit not in the reference, or only in a turnaround sheet | Attach a clean full-body outfit image and cite it inside the subject | Make the outfit plate with `qwen-image-edit-2-1` |
| Two people merge or swap faces | Similar descriptions; labels not repeated in each shot | Repeat `<Subject N>` at each action; give them different positions (`on her right side`) | Gender-filtered ReActor passes |
| Blank, dead faces | No expression clause | Add one per readable face ([06-expressions-and-delivery.md](06-expressions-and-delivery.md)) | — |
| Mouth keeps moving after the line | No mouth closure | `She closes her lips…` after `</d>`; listeners `lips stay closed` | — |

## People, rooms and props

| Symptom | Fix |
|---|---|
| Extra people appear | Use an empty location image (architecture and light only); say `the corridor is otherwise empty`; extras `softly out of focus` if wanted |
| Invented room / wrong set | Attach the location as `<Subject N>` with `fully_preserved`; for the exact camera view, add a standalone `<Picture N>` composition anchor |
| Door opens the wrong way / teleports | Describe the hinge side and direction once: `pulls the door toward himself, hinged on the left`; give the door its own beat |
| Person walks through the camera | `stopping in a clear medium framing` |
| Props vanish | Mention the prop in every shot where it is visible |

## Camera

| Symptom | Fix |
|---|---|
| Move ignored | Use the official verb from [03-camera-motions.md](03-camera-motions.md), not a synonym |
| Two moves cancel / jitter | One move per shot; split into shots |
| Camera loses the subject | `The camera tracks <Subject 1> … and keeps him centered throughout`; or end the shot with `The camera never leaves <Subject 1>.` |
| Front tracking distorts faces | `medium shot` → `medium-wide shot`; add `steady distance`; slow speed |

## Audio and dialogue

| Symptom | Fix |
|---|---|
| Wrong language or accent | Native script inside `<d>`; correct `[Language]`; accent clause from [05-voice-library.md](05-voice-library.md) |
| Voice changes between shots | Same `(Sx)` and same voice wording in every shot; or attach `<Audio N>` |
| Line cut off | Shot too short for the line: extend the shot or the clip ([04-framing-and-timing.md](04-framing-and-timing.md) §Shot count) |
| Wrong person speaks | `<Subject N> (Sx)` right before the verb; only the speaker's face front-facing; listener `lips stay closed` |
| Music too loud / unwanted | `non_diegetic_music: N/A` or a quieter description |
| Total silence wanted | `overall_soundscape: N/A` and `non_diegetic_music: N/A` |

## Format and label errors

| Error | Fix |
|---|---|
| API error mixing roles | `reference_*` and `first_frame`/`last_frame` cannot be combined: choose Ref2VA or I2VA |
| T2VA rejected with `adaptive` ratio | Give a concrete ratio |
| Prompt rejected or truncated | Keep text ≤ 7000 characters |
| `<Image N>` used | The official label is `<Picture N>` |
| Label in summary not defined | Define every label in `subject_definitions` first; the summary introduces none |
| Label numbers do not match uploads | `<Picture N>` = Nth attached image; `<Video N>` and `<Audio N>` count separately |
| `(Sx)` in retention_analysis | Remove; speaker IDs only in descriptions and audio definitions |
| `detailed_description` in T2VA, or `integrated_multimodal_description` in Ref2VA | Use the mode skill's template |
| First shot has a timestamp, or `00:03:000` | `[Shot 1]` untimed; `00:03.000` |
| Cut time ≥ duration | Recompute timing |
| HTTP 422 sensitive content | Soften violent or explicit wording; describe consequences instead of gore |
| Markdown or bullets inside the prompt | Plain text only, sections as in the template |
