# 14 — Style: noir thriller

A style layer. The mode skill owns the format; the core skill owns framing and camera rules.

## Opening sentence

- **Ref2VA:**
  `The target video is in a neo-noir crime-thriller style with hard low-key lighting, deep black shadows, sodium-orange and cold cyan accents, wet reflective surfaces, light film grain, and natural proportions.`
- **T2VA / I2VA:**
  `[Shot 1] Live-action, cinematic neo-noir look with hard low-key lighting and deep shadows, a medium close-up frames…`

## Look

| Element | Vocabulary |
|---|---|
| Lighting | single hard source; `shadows of window blinds striping her face`, `the shadow of cell bars across the wall`; under-lit or side-lit faces; smoke or haze in the beam |
| Color | near-monochrome with one accent: sodium orange streetlight, cyan neon, a red tail-light |
| Surfaces | rain-wet streets, glossy reflections, sweating walls |
| Lens | `85mm` close-ups with half the face in shadow; `50mm` mediums; deep focus for paranoia beats |
| Camera | slow push-ins, static holds, slight Dutch angle (`a tilted Dutch-angle medium shot`), POV through bars or blinds; tracking from behind in alleys |
| Performance | still, guarded, minimal blinking; menace through slowness |

## Sound

- Soundscape: rain, dripping water, distant sirens, a buzzing neon tube, footsteps in an empty alley.
- Score: `a slow pulsing synth bass`, `muted trumpet phrases`, `brushed snare at a slow tempo`, `low drones that cut out before the reveal`.

## Do / don't

- Do: keep at least one eye and the mouth lit on a speaking face, so identity and lip-sync read.
- Do: use shadows on walls to tell story (bars, blinds, a figure).
- Don't: bright high-key light, saturated rainbow neon, fast camera, comedy beats.

---

## Worked example

### Ref2VA, 8 s; attach image 1 = officer, image 2 = cell-block corridor; voice **M1**

```text
subject_definitions:
<Subject 1> is the officer in <Picture 1>, with his face, hair, build, and complete uniform taken exactly from the reference.
<Subject 2> is the cell-block corridor in <Picture 2>, with its bars, wet floor, and caged ceiling lamps exactly as shown.

summary:
[reference generation] In one shot in <Subject 2> at night, <Subject 1> walks slowly toward the camera through bars of shadow, stops in close-up, and delivers a quiet warning.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - his identity, face, hair, build, and full uniform are retained without changes.
<Subject 2> (appears in [Shot 1]): fully_preserved - the bars, wet floor, and ceiling lamps are retained without changes.

detailed_description:
The target video is in a neo-noir crime-thriller style with hard low-key lighting, deep black shadows, sodium-orange and cold cyan accents, wet reflective surfaces, light film grain, and natural proportions.
[Shot 1] A medium shot at eye level, shot on a 50mm lens, frames <Subject 1> walking slowly toward the camera down the center of <Subject 2>, the shadows of the cell bars sliding across his body as he passes under each caged sodium lamp. The wet floor reflects the orange light. The camera pushes in at slow speed as he approaches and stops in a close-up, front-facing, half of his face in shadow, one eye and his mouth lit. His expression is cold and patient. <Subject 1> (S1) says in a deep, gravelly middle-aged male voice with a slow, measured pace, barely above a murmur, <d>[Kannada] ಇಲ್ಲಿ ಗೋಡೆಗಳಿಗೂ ಕಿವಿ ಇದೆ.</d> He closes his lips and holds the stare without blinking.

overall_soundscape:
Water drips steadily somewhere in the dark, his boots tap slowly on the wet floor, a sodium lamp buzzes, and a distant cell door rattles once.

non_diegetic_music:
A slow pulsing synth bass with a single muted trumpet phrase, cutting out just before his line.
```

(`ಇಲ್ಲಿ ಗೋಡೆಗಳಿಗೂ ಕಿವಿ ಇದೆ.` = "Here, even the walls have ears.")
