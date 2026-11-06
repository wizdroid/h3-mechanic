# 09 — I2VA / FL2VA / L2VA (first/last-frame modes)

Source format: MiniMax H3 "Video Prompt Writing Guide (T2VA / I2VA / FL2VA / L2VA)".

Use when an image **is the literal frame** (opening, ending, or both). If a style skill is in play, match it to what the image already shows — **the image's look wins**.

## Which sub-mode

| Images | Sub-mode | API roles |
|---|---|---|
| 1, opening | **I2VA** | `first_frame` (default for a single image) |
| 2, opening + ending | **FL2VA** | `first_frame` + `last_frame` |
| 1, ending | **L2VA** | `last_frame` |

Frame images cannot be combined with reference images, videos or audio. Everyone who must look exact has to be in the frame image already. Ratio always follows the image (`adaptive`).

## The instruction line (first line, verbatim, then one blank line)

**I2VA**

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
```

**FL2VA**

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.
```

**L2VA**

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.
```

- `N` is the index of the actual final shot. `S.SS` is the clip duration with exactly two decimals (`8.00`).
- Copy the punctuation and brackets exactly as shown; the FL2VA line has **no** angle or square brackets.

## Then the three fields

```text
integrated_multimodal_description: [Shot 1] Live-action, cinematic, the subject shown in <Picture 1> … (style, then what the frame shows, then the action)

overall_soundscape: …

non_diegetic_music: …
```

## How to write the path

- **I2VA:** first-frame anchor → action onset → continuous development → result or reaction. Open by restating the style and what `<Picture 1>` shows (subjects, positions, clothing, setting) and keep identity, colors, key objects and spatial layout consistent.
- **FL2VA:** first-frame state → visible intermediate changes → narrowing differences → last-frame state. Prefer **one shot** so H3 interpolates continuously; use several only when the user asks. The final `[Shot N]` must land on Picture 2 at the end. Describe the motion **between** the frames, not two static images.
- **L2VA:** plausible earlier state → explicit action and transition → gradual convergence in the final shot → lands on `<Picture 1>` at the end.
- Camera, dialogue, voices and framing follow the core rules. Do not cut to a framing the image cannot support (a wide of a face that is a close-up in the frame).

## Output

The prompt in one ```text fence, then: sub-mode, duration, resolution, which file is first/last frame, voice IDs.

---

## Worked examples

### 1. I2VA: guilty convict on the cell floor, slow push-in, Kannada mumble (8 s)

First frame: the convict sitting on the cell floor against the wall, medium shot. Voice **F6**. Settings: 8 s, 2K.

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, the young woman shown in <Picture 1> remains seated on the concrete floor of the cell with her back against the grey wall and her knees drawn up, preserving her appearance, clothing, position, and the cell layout and cold top light. The camera pushes in with small amplitude at slow speed from the medium shot toward a medium close-up of her face, which stays front-facing and natural. She stares at her hands resting on her knees, her eyes glistening, her lips pressed together. Her breath shudders once. The young woman with a thin, fragile voice and a slight tremble (S1) mumbles quietly, the words trailing off, <d>[Kannada] ನಾನು ಹೀಗೆ ಮಾಡಬಾರದಿತ್ತು.</d> She closes her lips, a single tear runs down her left cheek, and she turns her face slightly toward the wall as the shot ends.

overall_soundscape: Quiet echoing cell room tone with a faint buzz from the ceiling light, her unsteady breathing, and distant footsteps somewhere down the corridor.

non_diegetic_music: A slow, sustained low string chord with a single soft piano note repeating every few seconds, decreasing in volume toward the end.
```

(`ನಾನು ಹೀಗೆ ಮಾಡಬಾರದಿತ್ತು.` = "I should not have done this.")

### 2. FL2VA: closed cell door to open cell door, single shot (6 s)

Picture 1: officer standing outside the closed cell door, keys in hand. Picture 2: the same door wide open, officer holding it, the corridor visible. Settings: 6 s, 768P, single shot so H3 interpolates continuously.

```text
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 6.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, the officer begins in the position and framing established by Picture 1, standing in a medium shot outside the closed barred cell door with a ring of keys in his right hand, his face stern and in three-quarter view. The camera holds a static shot. He selects one key, slides it into the lock, and turns it with a firm twist; the bolt releases with a heavy clack. He grips a bar with his left hand and pulls the door toward himself; the door swings open on its hinges in one slow, steady arc while he steps half a pace back to make room. His expression stays strict and focused throughout. The door comes to rest fully open, and he settles into the stance, hand position, door angle, and composition established by Picture 2 at the end of the shot.

overall_soundscape: Keys jingle, the lock turns with a heavy metallic clack, and the hinges creak long and low as the door swings open in an echoing concrete corridor.

non_diegetic_music: N/A
```

### 3. L2VA: ending on the woman alone at the cell window (7 s)

Picture 1 (last frame): the woman in side profile at the barred window, light on her face. Settings: 7 s, 2K.

```text
How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the 7.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, a medium shot begins with the same woman visible in <Picture 1>, in the same plain clothing, sitting on the narrow cot on the far side of the cell, her head bowed, the barred window above her empty of direct light. The camera holds a static shot. She lifts her head as a pale beam of morning light slides through the window bars onto the wall. She rises slowly, crosses the cell in three unhurried steps, and stops beneath the window, turning into side profile. Her guarded expression softens, her eyes lift toward the light, and her lips part slightly. Toward the end, she raises one hand to rest on the sill and settles into the exact posture, profile angle, light on her face, and final composition established by <Picture 1>.

overall_soundscape: Quiet cell room tone, the creak of the cot as she rises, soft bare footsteps on concrete, and birdsong faintly audible through the window.

non_diegetic_music: A single sustained violin note at a slow tempo, joined by a gentle harp arpeggio as she reaches the window.
```
