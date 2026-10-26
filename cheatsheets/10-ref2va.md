# 10 — Ref2VA (full-reference mode)

Source format: MiniMax H3 "Full-Reference Mode Rewrite Output Format Guide".

Use when references are **not** the literal frame: character, location, prop, motion or voice references. Follow the core rules (limits, grammar, pre-flight). If a style skill is in play, use its opening sentence and vocabulary.

## Procedure

1. **Attach map.** List every reference in upload order and give it a label. Images become `<Picture 1>…`, videos `<Video 1>…`, audio `<Audio 1>…`, each numbered separately in its own upload order. Ask only if the order is unknown and matters.
2. **Subjects.** Each person, outfit, location or prop that must be tracked becomes a `<Subject N>`, defined from its source (`<Subject 1> is the man in <Picture 1>, …`). A `<Picture N>` gets its own line only when it is a concrete frame (first frame, keyframe, last frame) or a composition / storyboard anchor.
3. **Identity wording.** Describe only what the image really shows. If the user says the references are complete, use identity-locked wording: `with his face, hair, build, and complete outfit taken exactly from the reference`. Do not invent hair or wardrobe details that could fight the image.
4. **Voices.** Assign `(S1)`, `(S2)`… in order of first vocal event. Voice comes from `<Audio N>` (`<Audio 1> is the voice-timbre reference for <Subject 1> (S1).`) or from the [voice library](05-voice-library.md). If the user has not chosen library voices, pick sensible IDs and say which ones you used.
5. **Shots.** Plan shot count, sizes, angles, one camera move each, and cut times with the [framing rules](04-framing-and-timing.md) and [motion rules](03-camera-motions.md).
6. **Write the six sections** in the template below. `detailed_description` is normally **350–500 English words** for generation tasks; dialogue-heavy clips prioritise fitting every line.
7. Run the [pre-flight check](16-preflight-checklist.md), then output.

## Template

```text
subject_definitions:
<Subject 1> is the … in <Picture 1>, …
<Subject 2> is the … in <Picture 2>, …
<Picture 3> is the composition anchor for [Shot 1], defining … (only if used as a frame or layout anchor)
<Audio 1> is the voice-timbre reference for <Subject 1> (S1). (only if audio is attached)

summary:
[task type + task type] One short paragraph using only the labels defined above: who, where, what happens, shot flow, and what each reference contributes.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - …
<Picture 3> ([Shot 1] composition anchor): fully_preserved - …
<Video 1> (camera path): weak_reference - …
<Audio 1>: reference - …

detailed_description:
The target video is … (one or two sentences: style, lighting, color, lens look).
[Shot 1] Composition and size, subject positions and labels, environment and light, action, one camera move, expressions, sounds, dialogue.
[Shot 2] At 00:05.000, the shot cuts to …

overall_soundscape:
…

non_diegetic_music:
…
```

Each section header is on its own line, followed by its content, with a blank line between sections.

## Summary task-type prefixes

One bracketed task type, or several joined with ` + `, never repeated.

| Type | When |
|---|---|
| `reference generation` | Images/video/audio guide character, scene, style, motion or camera, without being a literal frame |
| `keyframe completion` | An image is a first frame, keyframe, last frame or other concrete frame/composition anchor |
| `video editing` | A source video is modified (summary then starts `The target video is an edited version of <Video 1>.`) |
| `video continuation` | New content continues from a source video |
| `audio reuse` | The same audio signal is reused |
| `audio reference` | Only voice timbre, style, rhythm or texture of the audio is followed |

## Retention markers

**Visual markers:** `fully_preserved` (identity must match), `partially_preserved` (used, some features changed), `attribute_transfer` (a feature moves to another subject, e.g. an outfit onto a different person), `weak_reference` (broad style/composition/motion only, e.g. a motion clip).

**Audio markers:** `fully_copy`, `partially_copy`, `reference`, `weak_reference`.

**Entry shapes:**

- `<Subject N> (appears in [Shot 1], [Shot 3]): marker - …`
- `<Picture N> ([Shot 1] first frame): marker - …`
- `<Video N> (cut and pacing structure): marker - …`
- `<Audio N>: marker - …`

## Rules specific to Ref2VA

- Never write `(Sx)` in `retention_analysis`.
- Do not count newly added actions or plot as a loss of fidelity.
- Style goes in one or two sentences **before** `[Shot 1]` and starts `The target video is …`.
- At a subject's first clear appearance in a shot, state its position and action. Later shots reuse the label without redefining it.
- Speaking subjects are written `<Subject N> (Sx)`. A speaker who is not a defined subject gets a stable voice description plus `(Sx)`.
- When only timbre is referenced from `<Audio N>`, do **not** carry its original words into the target video.
- Frame-anchor phrases: `the shot begins from <Picture 1>`, `the shot's keyframe corresponds to <Picture 2>`, `the shot ends on <Picture 3>`.
- Budget: ≤ 9 images, ≤ 3 videos, ≤ 3 audio, ≤ 12 files.

## Project mode (short-film repos)

If the working directory is a short-film project with a `production/` folder, read `production/prompts/clip-prompt-reference.md`, `PLATES.txt` and sibling `clip-*.txt` files in the scene folder first, and keep the attach order those files define. Write the clip to the scene folder only when the user asks to save it.

## Output

1. Attach order table (label → file or description; `MISSING` for anything the scene needs but the user lacks).
2. The prompt in one ```text fence.
3. Settings: duration, resolution, ratio, voice IDs.
4. Up to two short tips or variations.

---

## Worked examples

### 1. Corridor escort: wide from behind, then medium tracking from the front (10 s, no dialogue)

Attach: image 1 = officer, image 2 = convict, image 3 = empty corridor. Settings: 10 s, 2K, 16:9.

```text
subject_definitions:
<Subject 1> is the officer in <Picture 1>, with his face, hair, build, and complete uniform taken exactly from the reference.
<Subject 2> is the woman in <Picture 2>, a convict, with her face, hair, build, and complete outfit taken exactly from the reference.
<Subject 3> is the prison corridor in <Picture 3>, including its walls, floor, ceiling lights, cell doors, and layout exactly as shown.

summary:
[reference generation] In two shots of one continuous scene, <Subject 1> escorts <Subject 2> down <Subject 3>, gripping her upper arm as they walk toward the far end. [Shot 1] is a wide tracking shot from behind, and [Shot 2] is a medium tracking shot from the front with the camera moving backward ahead of them.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - his identity, face, hair, build, and full uniform are retained without changes.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - her identity, face, hair, build, and full outfit are retained without changes.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - the corridor's walls, floor, lighting, cell doors, and layout are retained without changes.

detailed_description:
The target video is realistic and cinematic, with a tense, serious mood, cold fluorescent overhead light, a muted grey-green palette, natural proportions, and smooth, steady camera movement.
[Shot 1] A wide shot from behind at eye level shows <Subject 1> and <Subject 2> walking away from the camera down the center of <Subject 3>, the long corridor stretching toward a distant barred gate. Their faces are not visible. <Subject 1> walks on her right side, half a step behind her shoulder, his left hand gripping her right upper arm firmly. <Subject 2> walks with her head slightly lowered, her steps short and measured, her free arm hanging still. Pools of cold light fall on the floor at regular intervals, and the closed cell doors pass on both sides. The camera tracks <Subject 1> and <Subject 2> from behind at slow speed, keeping a steady distance and both full bodies centered in the frame.
[Shot 2] At 00:05.000, the shot cuts to a medium shot from the front at eye level, framing both of them from the waist up as they walk toward the camera, shot on a 50mm lens with compressed perspective. The camera tracks them from the front, moving backward ahead of them at the same pace and keeping a steady distance so their faces stay clear, natural, and undistorted. <Subject 1> keeps his grip on her upper arm, his jaw set, his eyes fixed ahead, his face stern and unreadable. <Subject 2> keeps her gaze low with a guarded, weary expression; once she glances briefly toward him, then looks down again, her lips pressed together. The corridor behind them falls into soft, shallow depth of field, the ceiling lights blurring into pale smudges. Their footsteps stay in rhythm until the end of the shot as they continue toward the far end.

overall_soundscape:
Their footsteps echo on the hard floor in a steady rhythm under a faint fluorescent hum and quiet corridor room tone. A distant metal door clangs once far behind them.

non_diegetic_music:
A low, sustained cello drone at a slow tempo with a soft pulse of muted timpani, staying quiet and even throughout.
```

### 2. Cell door, filmed from inside the cell, Kannada command (8 s)

Attach: image 1 = officer, image 2 = convict, image 3 = photo taken from inside the empty cell looking at the door. No audio, so the officer uses library voice **M5**. Settings: 8 s, 2K, adaptive.

```text
subject_definitions:
<Subject 1> is the officer in <Picture 1>, with his face, hair, build, and complete uniform taken exactly from the reference.
<Subject 2> is the woman in <Picture 2>, a convict, with her face, hair, build, and complete outfit taken exactly from the reference.
<Subject 3> is the prison cell interior in <Picture 3>, including its bars, door, walls, floor, and lighting exactly as shown.
<Picture 3> is the composition anchor for [Shot 1], defining the camera position inside the cell, the viewpoint, and the framing toward the cell door.

summary:
[reference generation + keyframe completion] In one static shot filmed from inside <Subject 3> with the framing of <Picture 3>, <Subject 1> unlocks and opens the cell door, orders <Subject 2> inside in Kannada, and she walks into the cell with a guilty expression while he watches strictly.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - his identity, face, hair, build, and full uniform are retained without changes.
<Subject 2> (appears in [Shot 1]): fully_preserved - her identity, face, hair, build, and full outfit are retained without changes.
<Subject 3> (appears in [Shot 1]): fully_preserved - the cell's bars, door, walls, floor, and lighting are retained without changes.
<Picture 3> ([Shot 1] composition anchor): fully_preserved - the camera position, viewpoint, and framing toward the door are retained throughout the shot.

detailed_description:
The target video is realistic and cinematic, with a tense, somber mood, harsh cold light from a single caged ceiling bulb, natural proportions, and a completely static camera.
[Shot 1] The shot begins from <Picture 3>, the view from deep inside <Subject 3> looking toward the closed barred door, and the camera holds a static shot at this position and framing for the entire clip. Beyond the bars, <Subject 1> and <Subject 2> walk into view in the corridor and stop in front of the door, his hand gripping her upper arm. <Subject 1> releases her, turns a key in the lock with a metallic clack, and pulls the door open toward himself with a long creak, then steps aside and holds it open. His jaw is set and his eyes are hard as he looks straight at her. <Subject 1> (S1) points into the cell and orders firmly in a hard, clipped mid-low male voice with a brisk staccato pace, <d>[Kannada] ಒಳಗೆ ಹೋಗು.</d> He closes his mouth and keeps his arm extended. <Subject 2> lowers her head, her eyes downcast, her lips pressed together, her shoulders slightly hunched with guilt. She hesitates for a moment on the threshold, then walks slowly into the cell toward the camera and stops in a clear medium framing, centered, her face natural and undistorted, still looking at the floor. Behind her, <Subject 1> remains in the open doorway, his strict expression unchanged, watching her as the shot ends.

overall_soundscape:
Echoing prison room tone with a faint electrical buzz from the bulb. The metallic clack of the lock, a loud creaking hinge, and slow footsteps on the concrete floor.

non_diegetic_music:
N/A
```

### 3. Office door: he holds it open, she looks at him with respect and quiet attraction (12 s, two shots)

Attach: image 1 = man, image 2 = woman, image 3 = the office door with its wall. Only the corridor beyond the door is imagined. Settings: 12 s, 2K, 16:9.

```text
subject_definitions:
<Subject 1> is the man in <Picture 1>, with his face, hair, build, and complete outfit taken exactly from the reference.
<Subject 2> is the woman in <Picture 2>, with her face, hair, build, and complete outfit taken exactly from the reference.
<Subject 3> is the office door in <Picture 3>, including its frame, handle, material, color, and the surrounding wall exactly as shown.

summary:
[reference generation] <Subject 1> and <Subject 2> walk side by side to <Subject 3>. In [Shot 1] the camera follows <Subject 1> as he opens the door for her. In [Shot 2], from the corridor beyond the door, <Subject 2> pauses to look at him with respect and quiet attraction.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - his identity, face, hair, build, and full outfit are retained without changes.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - her identity, face, hair, build, and full outfit are retained without changes.
<Subject 3> (appears in [Shot 1], [Shot 2]): fully_preserved - the door's design, handle, frame, color, and surrounding wall are retained without changes.

detailed_description:
The target video is realistic and cinematic, with soft natural office daylight, warm skin tones, shallow depth of field, natural proportions, and smooth, steady camera work.
[Shot 1] A medium shot from slightly behind and to the side of <Subject 1>, shot on a 50mm lens, shows him walking at a calm, confident pace beside <Subject 2> across the office floor toward <Subject 3> at the far side of the frame. The camera tracks <Subject 1> smoothly from behind at a steady distance, keeping him centered. At the door he steps half a pace ahead, takes the handle, pulls the door open toward himself, and stands to the side holding it with one hand, his face in three-quarter view with a slight, polite smile.
[Shot 2] At 00:05.500, the camera cuts to the bright corridor beyond the door, looking back at the doorway in a medium close-up at eye level, shot on an 85mm lens. The corridor has large windows and warm daylight across a light floor. The camera holds a static shot. <Subject 2> pauses on the threshold, front-facing, and turns her head to look at <Subject 1>. Her eyes linger on him a moment longer than needed, a small, warm, respectful smile forms, and she lowers her gaze softly before stepping through the doorway past the camera's left side. <Subject 1>, still holding the door, watches her pass with a gentle smile, then walks through after her into a clear medium framing, turns back, and pulls <Subject 3> closed behind him with a controlled motion. The shot ends with the door fully closed and <Subject 1> turning to walk on down the corridor.

overall_soundscape:
Quiet office room tone and soft footsteps on the floor, the click of the door handle, a gentle door swing, and a soft latch as the door closes. Faint corridor air conditioning hums beyond the door.

non_diegetic_music:
A light solo piano figure at a moderate tempo with soft sustained strings entering as she pauses, then fading gently by the end.
```

### 4. Interrogation, shot–reverse–shot, officer voice from reference audio, convict from the library (12 s, Kannada)

Attach: image 1 = officer, image 2 = convict, image 3 = interrogation room; audio 1 = 6 s clip of the officer actor's voice. Convict uses library voice **F6** with the Bengaluru accent clause. Settings: 12 s, 2K, 16:9.

```text
subject_definitions:
<Subject 1> is the officer in <Picture 1>, with his face, hair, build, and complete uniform taken exactly from the reference.
<Subject 2> is the woman in <Picture 2>, a convict, with her face, hair, build, and complete outfit taken exactly from the reference.
<Subject 3> is the interrogation room in <Picture 3>, with its bare walls, metal table, two chairs, and single hanging lamp exactly as shown.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[reference generation + audio reference] Across three shots in <Subject 3>, <Subject 1> demands the truth from <Subject 2> in Kannada, using <Audio 1> as his voice-timbre reference. <Subject 2> denies it in a fragile voice, and the clip ends on <Subject 1>'s unconvinced reaction.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - his identity, face, hair, build, and full uniform are retained without changes.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - her identity, face, hair, build, and full outfit are retained without changes.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - the walls, metal table, chairs, and hanging lamp are retained without changes.
<Audio 1>: reference - the officer's spoken delivery follows the voice timbre of <Audio 1> without copying the original signal or its words.

detailed_description:
The target video is realistic and cinematic, with a claustrophobic mood, a single hard top light from the hanging lamp, deep shadows on the walls, desaturated colors, natural proportions, and steady framing.
[Shot 1] A medium close-up at eye level, shot on an 85mm lens, frames <Subject 1> from the chest up, front-facing, seated across the metal table, with the softly blurred shoulder of <Subject 2> in the left foreground. The lamp throws hard light across his brow. The camera holds a static shot. He leans forward, rests his forearms on the table, and his eyes narrow. <Subject 1> (S1) asks sharply in the voice timbre referenced from <Audio 1>, each word clipped, <d>[Kannada] ಸತ್ಯ ಹೇಳು. ಆ ರಾತ್ರಿ ನೀನು ಎಲ್ಲಿದ್ದೆ?</d> He closes his mouth and waits, unblinking.
[Shot 2] At 00:04.500, the camera cuts to a medium close-up of <Subject 2>, front-facing over the softly blurred shoulder of <Subject 1>. Her eyes are glistening and fixed on the table, her fingers twisting together. The camera pushes in with small amplitude at slow speed toward her face. <Subject 2> (S2) mumbles in a thin, fragile young female voice with a slight tremble, speaking Kannada with a natural Bengaluru urban accent, the words trailing off, <d>[Kannada] ನಾನು ಏನೂ ಮಾಡಿಲ್ಲ, ಸರ್.</d> She closes her lips, swallows hard, and cannot raise her eyes.
[Shot 3] At 00:09.000, the camera cuts to a close-up of <Subject 1>, front-facing. The camera holds a static shot. His lips stay closed; he studies her in silence, one corner of his mouth tightening, his eyes cold and unconvinced, and he slowly leans back into the shadow.

overall_soundscape:
Low room tone, the faint buzz of the hanging lamp, the creak of a chair as he leans forward and back, and her shaky breathing between lines.

non_diegetic_music:
A single low synth drone at a slow tempo with sparse, muted heartbeat-like bass pulses that stop abruptly at the final cut.
```
