# 12 — Style: cinematic modern

A style layer. The mode skill owns the format; the core skill owns framing and camera rules. This skill only sets the look and sound.

## Opening sentence

- **Ref2VA** (before `[Shot 1]`):
  `The target video is in a modern cinematic feature-film style with motivated low-key lighting, a teal-and-amber color grade, rich contrast, fine film grain, shallow depth of field, and natural proportions.`
- **T2VA / I2VA** (start of `[Shot 1]`):
  `[Shot 1] Live-action, cinematic, modern feature-film look with motivated low-key lighting and shallow depth of field, a medium close-up frames…`

## Look

| Element | Vocabulary |
|---|---|
| Lighting | motivated by practicals (window, lamp, neon, fire); soft key from one side, deep negative fill; rim light separating the subject; volumetric haze in light shafts |
| Color | teal-and-amber grade, warm skin tones against cool shadows; or monochrome-leaning single-hue scenes (all blue night, all amber interior) |
| Lens | `shot on an 85mm lens` for faces, `50mm` for mediums, `anamorphic-style oval bokeh and subtle horizontal flares` |
| Texture | `fine film grain`, `gentle halation around highlights` |
| Ratio | `21:9` for T2VA/Ref2VA; 16:9 when the user's edit is 16:9 |
| Camera | slow push-ins, smooth tracking, static holds on performance, occasional slow arc. Speed `at slow speed` by default |
| Performance | restrained and internal; emotion in the eyes; few words |
| Dialogue delivery | low, natural, close-mic intimacy |

## Sound

- Soundscape: detailed and layered (room tone, cloth, breath, distant city), with silence used before big lines.
- Score: `sustained low strings`, `sparse piano`, `analog synth pads`, `slow pulsing bass`, building or dropping out; write instrumentation, tempo and dynamics only.

## Do / don't

- Do: one light source named per shot; let shadows hide part of the face only in CU/MCU; land moves on the face or a key object.
- Do: hold faces at CU/MCU/MS per the core rules; widescreen does not mean wide shots.
- Don't: `epic`, `8k`, `masterpiece`, lens-flare everywhere, fast whip pans on faces, crash zooms (that is the 80s look).

---

## Worked examples

### 1. Ref2VA: rooftop at night, a decision (10 s)

Attach: image 1 = man, image 2 = rooftop location. Voice **M2**. Settings: 10 s, 2K, 21:9.

```text
subject_definitions:
<Subject 1> is the man in <Picture 1>, with his face, hair, build, and complete outfit taken exactly from the reference.
<Subject 2> is the city rooftop in <Picture 2>, with its parapet, water tank, and distant skyline exactly as shown.

summary:
[reference generation] In two shots on <Subject 2> at night, <Subject 1> stands at the parapet looking over the city, then turns in close-up and makes a quiet decision aloud.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - his identity, face, hair, build, and full outfit are retained without changes.
<Subject 2> (appears in [Shot 1], [Shot 2]): fully_preserved - the parapet, water tank, and skyline are retained without changes.

detailed_description:
The target video is in a modern cinematic feature-film style with motivated low-key lighting, a teal-and-amber color grade, rich contrast, fine film grain, shallow depth of field, and natural proportions.
[Shot 1] A wide shot from behind at eye level shows <Subject 1> standing at the parapet of <Subject 2>, his back to the camera and his face not visible, the city skyline glittering in cool teal haze beyond him. Warm amber light from a single bulb above the stairwell door rims his shoulders. Wind moves his clothing slightly. The camera pushes in with small amplitude at slow speed toward him, holding him centered.
[Shot 2] At 00:05.000, the camera cuts to a close-up of <Subject 1>, front-facing, shot on an 85mm lens with anamorphic-style oval bokeh of the city lights behind him. The camera holds a static shot. The amber rim light traces his cheek while the rest of his face sits in soft shadow. His eyes are fixed on something far away, then his jaw sets with quiet determination. <Subject 1> (S1) says in a smooth, resonant baritone male voice with a steady, confident pace, low and close, <d>[English] Tonight, it ends.</d> He closes his lips and holds the stare.

overall_soundscape:
Wind gusts across the rooftop under a distant hum of city traffic, a far-off siren, and the faint flap of his jacket.

non_diegetic_music:
Sustained low strings at a slow tempo with a pulsing analog synth bass that swells slightly before dropping out after his line.
```

### 2. T2VA: kitchen, early morning, a mother's quiet worry (8 s)

Voice **F3**. Settings: 8 s, 2K, 21:9.

```text
integrated_multimodal_description: [Shot 1] Live-action, cinematic, modern feature-film look with motivated low-key lighting and shallow depth of field, a medium close-up at eye level, shot on an 85mm lens with natural proportions, frames an Indian woman in her late thirties with her hair in a loose braid and a pale green cotton nightie under a grey shawl, standing at a small kitchen window holding a steel tumbler of coffee. Cool blue dawn light comes through the window and a warm amber glow from a gas stove flame lights her face from below. Steam curls from the tumbler. The camera holds a static shot. Her brows are drawn slightly together and her eyes watch the empty lane outside. She glances at a phone on the counter, its screen dark. The woman in a warm, velvety voice with a calm, even pace (S1) murmurs softly to herself, <d>[Kannada] ಇನ್ನೂ ಬಂದಿಲ್ಲ.</d> She closes her lips and tightens the shawl around her shoulders, her worry deepening as the shot ends.

overall_soundscape: The soft hiss of the gas flame, a distant rooster, a scooter passing in the lane, and the faint clink of the steel tumbler against her ring.

non_diegetic_music: A sparse solo piano at a slow tempo with soft analog synth pads entering underneath and staying quiet.
```

(`ಇನ್ನೂ ಬಂದಿಲ್ಲ.` = "Still hasn't come.")
