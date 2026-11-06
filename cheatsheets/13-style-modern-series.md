# 13 — Style: modern series

A style layer. The mode skill owns the format; the core skill owns framing and camera rules.

## Opening sentence

- **Ref2VA:**
  `The target video is in a modern streaming-drama style with naturalistic soft lighting, a muted, slightly desaturated color grade, realistic skin texture, gentle contrast, and natural proportions.`
- **T2VA / I2VA:**
  `[Shot 1] Live-action, streaming-drama look with naturalistic soft lighting and a muted grade, a medium close-up frames…`

## Look

| Element | Vocabulary |
|---|---|
| Lighting | soft daylight through windows, overcast exteriors, practical lamps at night; low contrast; faces evenly readable |
| Color | muted, slightly desaturated; cool greys and greens by day, sodium-amber streetlight by night |
| Lens | `50mm` mediums and `85mm` close-ups, moderate depth of field (backgrounds readable, not creamy) |
| Ratio | `16:9` (or `2:1`-feel via 21:9 if the user wants a premium look) |
| Camera | coverage: MCU singles, over-the-shoulder, MS two-shots; `the camera shakes slightly` for handheld intimacy; static for confrontations; slow push-in for the key line |
| Editing rhythm | 2–3 shots per clip, shot–reverse–shot on dialogue, reaction inserts |
| Performance | understated, naturalistic, overlapping glances; emotion shown, rarely stated |
| Dialogue delivery | conversational, natural volume, mixed Kannada/English where real people would mix |

## Sound

- Soundscape: realistic location sound (fans, traffic through windows, phones buzzing, pressure-cooker whistle in Indian homes).
- Score: minimal; `soft ambient synth pad`, `muted electric guitar harmonics`, `low pulse`; often `N/A` for dialogue scenes.

## Do / don't

- Do: keep faces readable and evenly lit; use OTS coverage for every exchange; one speaker per shot.
- Do: let props and real locations carry realism (plastic chairs, tube lights, file stacks in a police station).
- Don't: heavy grain, teal-orange extremes, crash zooms, theatrical dialogue, big orchestral swells.

---

## Worked examples

### 1. Ref2VA: police station, woman officer and the convict, OTS coverage (12 s)

Attach: image 1 = woman officer, image 2 = convict, image 3 = police station room. Voices: officer **F5**, convict **F4**. Settings: 12 s, 2K, 16:9.

```text
subject_definitions:
<Subject 1> is the woman officer in <Picture 1>, with her face, hair, build, and complete uniform taken exactly from the reference.
<Subject 2> is the woman in <Picture 2>, a convict, with her face, hair, build, and complete outfit taken exactly from the reference.
<Subject 3> is the police station room in <Picture 3>, with its desk, file stacks, tube light, and ceiling fan exactly as shown.

summary:
[reference generation] In three shots of shot–reverse–shot coverage in <Subject 3>, <Subject 1> questions <Subject 2> across a desk, <Subject 2> answers with quiet defiance, and <Subject 1> reacts.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - her identity, face, hair, build, and full uniform are retained without changes.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - her identity, face, hair, build, and full outfit are retained without changes.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - the desk, file stacks, tube light, and ceiling fan are retained without changes.

detailed_description:
The target video is in a modern streaming-drama style with naturalistic soft lighting, a muted, slightly desaturated color grade, realistic skin texture, gentle contrast, and natural proportions.
[Shot 1] A medium close-up at eye level over the softly blurred shoulder of <Subject 2>, shot on an 85mm lens, frames <Subject 1> front-facing behind the desk in <Subject 3>, a tube light above and a slow ceiling fan casting faint moving shadows. The camera shakes slightly, handheld and close. She taps a file with one finger, her expression calm but probing. <Subject 1> (S1) asks in a crisp, authoritative mid-low female voice with precise diction and a measured pace, <d>[Kannada] ಆ ದಿನ ನೀನು ಯಾರನ್ನು ಭೇಟಿಯಾದೆ?</d> She closes her lips and waits.
[Shot 2] At 00:04.500, the camera cuts to a medium close-up of <Subject 2>, front-facing over the softly blurred shoulder of <Subject 1>. The camera shakes slightly. She lifts her chin and holds the officer's stare without blinking, her lips pressing into a hard line before she answers. <Subject 2> (S2) replies in a low, husky female voice with a slightly smoky texture and an unhurried pace, <d>[Kannada] ಯಾರನ್ನೂ ಭೇಟಿಯಾಗಿಲ್ಲ, ಮೇಡಂ.</d> She closes her lips and looks away toward the window.
[Shot 3] At 00:09.000, the camera cuts to a close-up of <Subject 1>, front-facing. The camera holds a static shot. Her lips stay closed; her eyes narrow slightly, and she slowly closes the file without looking down.

overall_soundscape:
The ceiling fan whirs steadily, traffic and a distant auto-rickshaw horn drift through the window, and paper rustles as the file closes.

non_diegetic_music:
N/A
```

(`ಆ ದಿನ ನೀನು ಯಾರನ್ನು ಭೇಟಿಯಾದೆ?` = "Who did you meet that day?" `ಯಾರನ್ನೂ ಭೇಟಿಯಾಗಿಲ್ಲ, ಮೇಡಂ.` = "No one, madam.")

### 2. T2VA: apartment balcony, a phone call at night (8 s)

Voice **M3** with a light Indian English accent. Settings: 8 s, 2K, 16:9.

```text
integrated_multimodal_description: [Shot 1] Live-action, streaming-drama look with naturalistic soft lighting and a muted grade, a medium shot at eye level, shot on a 50mm lens with natural proportions, frames an Indian man in his early thirties with short hair and a light stubble, in a grey T-shirt, standing on a small apartment balcony at night with a phone to his ear. Sodium-amber streetlight from below and the cool glow of the living room behind him light his face evenly. Potted plants and a drying rack with clothes stand beside him. The camera pushes in with small amplitude at slow speed toward a medium close-up. He listens, his brows tightening, then he rubs his forehead. The young man in a warm, gentle voice with a soft husk and a relaxed pace, with a light Indian English accent (S1) says quietly, <d>[English] Okay. I'll be there in twenty minutes.</d> He lowers the phone, closes his lips, and stares at the street below, worry settling on his face.

overall_soundscape: Distant traffic and dogs barking far away, a pressure-cooker whistle from a neighboring flat, and the faint buzz of the phone call ending.

non_diegetic_music: A soft ambient synth pad at a slow tempo with muted electric guitar harmonics, staying low under the scene.
```
