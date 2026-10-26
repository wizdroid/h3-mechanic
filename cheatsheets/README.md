# MiniMax H3 — Prompt Cheat-Sheets

Everything you need to write, audit, or fix a MiniMax H3 video prompt. Compiled from the `h3-*` skills: `h3-core`, `h3-t2va`, `h3-i2va`, `h3-ref2va`, and the four `h3-style-*` layers.

## The one-minute version

1. **Pick the mode** from what you actually have (see [01-modes-and-hard-limits.md](01-modes-and-hard-limits.md)).
2. **Follow the shared grammar** — shot tags, camera verbs, speaker IDs, `<d>` dialogue, soundscape/music fields (see [02-shared-grammar.md](02-shared-grammar.md)).
3. **Use the mode's exact template** — [08-t2va.md](08-t2va.md), [09-i2va-fl2va-l2va.md](09-i2va-fl2va-l2va.md), or [10-ref2va.md](10-ref2va.md).
4. **Run the pre-flight check** before returning any prompt (see [16-preflight-checklist.md](16-preflight-checklist.md)).

## Index

| # | Sheet | Contents |
|---|-------|----------|
| 01 | [modes-and-hard-limits](01-modes-and-hard-limits.md) | Mode decision table, MiniMax API limits (duration, resolution, ratio, file counts) |
| 02 | [shared-grammar](02-shared-grammar.md) | Rules common to all modes: fields, shots, speakers, dialogue, soundscape, music, house audio rule |
| 03 | [camera-motions](03-camera-motions.md) | Official camera-move verbs, named moves mapped to H3 wording, beat → move picker, face-safety rules |
| 04 | [framing-and-timing](04-framing-and-timing.md) | Shot sizes, the face rules, angles, shot count per duration, cut-time math, coverage patterns, phrase bank |
| 05 | [voice-library](05-voice-library.md) | Full voice-timbre library: F1–F10, M1–M11, K1–K2, accent clauses, paste-ready phrases |
| 06 | [expressions-and-delivery](06-expressions-and-delivery.md) | Facial expressions, emotion transitions, vocal tones/deliveries, mouth discipline |
| 07 | [languages-and-on-screen-text](07-languages-and-on-screen-text.md) | `<d>` dialogue tags, ready native-script lines, on-screen text, subtitle policy |
| 08 | [t2va](08-t2va.md) | Text-to-video-with-audio: procedure, template, 3 worked examples |
| 09 | [i2va-fl2va-l2va](09-i2va-fl2va-l2va.md) | First/last-frame modes: instruction lines, templates, 3 worked examples |
| 10 | [ref2va](10-ref2va.md) | Full-reference mode: six-section format, markers, task types, 4 worked examples |
| 11 | [style-80s-bollywood](11-style-80s-bollywood.md) | 1980s Hindi masala-film look + example |
| 12 | [style-cinematic-modern](12-style-cinematic-modern.md) | Modern feature-film look + example |
| 13 | [style-modern-series](13-style-modern-series.md) | Streaming/prestige drama look + example |
| 14 | [style-noir-thriller](14-style-noir-thriller.md) | Neo-noir crime-thriller look + example |
| 15 | [troubleshooting](15-troubleshooting.md) | Fix tables: faces, identity, rooms/props, camera, audio, format/label errors |
| 16 | [preflight-checklist](16-preflight-checklist.md) | The 8-point check to run before returning any prompt |

## The production pipeline these prompts plug into

Assets flow in one direction:

```
Krea2 character sheets  →  Qwen Image Edit 2.1 first frames  →  H3 video
```

Assume a character sheet and a first frame exist unless told otherwise. Prompt files are plain text named `clip-<NN>-<D>s.txt`; the duration comes from the filename and is capped at 15 s. `batch-scenes` / `batch-images` queue them into ComfyUI.

## House audio rule (default for every prompt)

Dialogue only:

- `overall_soundscape: N/A`
- `non_diegetic_music: N/A`
- No sound descriptions inside shots
- End the style opening sentence with:

> The audio contains only the spoken dialogue, with no background music, no ambience, and no sound effects.

Only add sound when the user explicitly asks for it in that prompt. This overrides any music/soundscape advice in the style sheets.
