# 02 — Shared grammar (all modes)

Rules that are the same in T2VA, I2VA, FL2VA, L2VA and Ref2VA.

## Language of the prompt

- Write **every field in English**.
- Only text inside `<d>…</d>` and on-screen text in `"double quotes"` stay in the original language and script (see [07-languages-and-on-screen-text.md](07-languages-and-on-screen-text.md)).

## Shots and timestamps

- `[Shot 1]` has **no timestamp**.
- Later shots start `[Shot N] At MM:SS.mmm, the camera cuts to …` with strictly increasing times inside the duration.
- Cut-time format is `MM:SS.mmm` — common typo: `00:03:000` must be `00:03.000`.
- One camera move per shot, worded with official verbs (see [03-camera-motions.md](03-camera-motions.md)). A second move is a new shot.

## Speakers

- Speakers get `(S1)`, `(S2)`… in order of **first vocal event**, keep the ID across shots.
- Non-speakers get no ID.
- Voice identity (age, pitch, timbre, pace, accent) and delivery go **outside** `<d>`; inside goes only `[Language]` plus the exact words.

  ```
  … (S1) says in a deep, gravelly middle-aged male voice with a slow, measured pace, <d>[Kannada] ಒಳಗೆ ಹೋಗು.</d>
  ```

- **Voiceover:** `says in an off-screen voiceover`, then add `while her lips remain completely closed` right after the `</d>`.

## Dialogue joins and cutoffs

- A line that crosses a cut: use `<scenetrans>` at both joins and state that the audio continues across the cut.
- A line cut off by the video end: use `<cutoff>`.

## Faces

- Every readable face gets an expression clause (see [06-expressions-and-delivery.md](06-expressions-and-delivery.md)).
- After a line ends, close the mouth explicitly (`she closes her lips`) so the face stops talking.

## Sound fields

- `overall_soundscape`: **1–4 sentences** of ambience, physical sounds and non-verbal human sounds. Use `N/A` only when the user wants total silence.
- `non_diegetic_music`: **1–3 sentences** of instrumentation, tempo and dynamics — **no mood words** (never "tense", "sad"). `N/A` when there is no score.
- Music the characters can hear (radio, a song being sung) goes in the **shot description**, not in `non_diegetic_music`.

## Concreteness

- Concrete beats abstract: name light sources, materials, distances, gestures.
- Do **not** stack tags like `4k, masterpiece`.

## House audio rule (overrides style-sheet audio advice)

Default to dialogue only:

- `overall_soundscape: N/A`
- `non_diegetic_music: N/A`
- No sound descriptions in shots
- End the style opening with: "The audio contains only the spoken dialogue, with no background music, no ambience, and no sound effects."

Only add sound when the user explicitly asks for it in that prompt.
