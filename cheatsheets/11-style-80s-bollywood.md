# 11 — Style: 80s Bollywood

A style layer. The mode skill owns the format; the core skill owns framing and camera rules. The face rules still apply — this era's zooms land on close-ups, which suits them.

## Opening sentence

- **Ref2VA:**
  `The target video is in the style of a 1980s Hindi masala film shot on 35mm, with visible film grain, a saturated warm Eastmancolor palette, soft diffusion glow on highlights, hard studio key lighting, slightly faded blacks, and natural proportions.`
- **T2VA / I2VA:**
  `[Shot 1] Vintage film, 1980s Hindi masala-film look on grainy 35mm with saturated warm colors and soft diffusion glow, a medium close-up frames…`

## Look

| Element | Vocabulary |
|---|---|
| Film | `visible 35mm film grain`, `slight gate weave`, `faded blacks`, `occasional dust specks`, `soft halation` |
| Color | saturated reds, magentas, emerald greens and golden yellows; warm skin; candy-colored set walls |
| Diffusion | `soft-focus diffusion filter glow`, `star-filter sparkles on lamps and jewellery` (romance and songs) |
| Lighting | hard frontal studio key, colored gel backlights (red, blue, green) in villain dens and discos; bright flat daylight outdoors |
| Lens / camera | zoom lenses: `The camera zooms in with large amplitude at fast speed onto <face>` (crash zoom) for shock and dialogue punches; slow `zooms in` for romance; static frontal compositions; low angle on the hero |
| Editing | reaction close-ups after each punchline; triple-cut emphasis is possible as three short shots (fits 6–10 s) |
| Ratio | `16:9` (or `4:3` for a TV-print feel) |

## Costumes and sets

- Hero: leather or denim jacket over open-collar shirt, wide collars, flared trousers, aviator sunglasses, thick moustache optional; police inspector in starched khaki with a peaked cap and lathi.
- Heroine: chiffon or sequined saree, puffed sleeves, big hair with side curls, bold eyeliner, large earrings and bangles; salwar kameez with dupatta in village scenes.
- Villain: safari suit or silk kurta, gold chains, rings, a cigar; henchmen in striped T-shirts and bandanas.
- Sets: villain den with smoke, colored gels and a revolving chair; police station with a wooden desk, rotary phone and a portrait on the wall; jail with painted grey bars; temples, havelis, Swiss-style meadows for songs.

## Performance and dialogue

- Theatrical and emphatic: punchline dialogues, a pause before the last word, eyes widening on the key word.
- Delivery wording: `declares in a booming, theatrical voice with a dramatic pause before the last word`, `says with heavy dramatic emphasis`, `roars`.
- Use M1, M2, M5, M6, F4, F7 from the [voice library](05-voice-library.md), plus the clause `speaking formal, theatrical Hindi`.
- Audio feel: `the voice sounds studio-dubbed, close and slightly reverberant` (80s post-synced dialogue).

## Sound and music

- Soundscape: exaggerated foley: `punchy dhishum punch impacts`, `whooshing swings`, `loud cloth swishes`, `ricochet gunshots`.
- Score: `dramatic string-section stings with a crashing cymbal on each zoom`, `synth-disco bass line with electronic drums and tabla`, `romantic shehnai and sitar with lush strings`, `harmonica motif for a lonely hero`. Write instrumentation, tempo and dynamics.

## Do / don't

- Do: crash zooms onto CU faces; saturated color; one bold gel light per shot.
- Do: keep villain-den wides from behind or establishing only.
- Don't: modern teal-orange grade, handheld shake (80s cameras were on tripods and trolleys), shallow creamy bokeh, smartphones, modern cars or LED lighting.
- Don't: zoom **out** from a speaking face into a wide.

---

## Worked example

### Ref2VA: inspector confronts the villain, crash zoom on the punchline (10 s, Hindi)

Attach: image 1 = inspector, image 2 = villain, image 3 = villain den. Voices: inspector **M2** + formal theatrical Hindi, villain **M6**. Settings: 10 s, 2K, 16:9.

```text
subject_definitions:
<Subject 1> is the police inspector in <Picture 1>, with his face, moustache, build, and complete khaki uniform taken exactly from the reference.
<Subject 2> is the villain in <Picture 2>, with his face, hair, build, safari suit, and gold chains taken exactly from the reference.
<Subject 3> is the villain's den in <Picture 3>, with its red and blue gel lights, smoke, and revolving chair exactly as shown.

summary:
[reference generation] In three shots inside <Subject 3>, <Subject 2> taunts <Subject 1>, <Subject 1> answers with a punchline delivered in theatrical Hindi, and the camera crash-zooms onto his face before a reaction close-up of <Subject 2>.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - his identity, face, moustache, build, and full uniform are retained without changes.
<Subject 2> (appears in [Shot 1], [Shot 3]): fully_preserved - his identity, face, hair, build, safari suit, and gold chains are retained without changes.
<Subject 3> (appears in [Shot 1], [Shot 2], [Shot 3]): fully_preserved - the gel lights, smoke, and revolving chair are retained without changes.

detailed_description:
The target video is in the style of a 1980s Hindi masala film shot on 35mm, with visible film grain, a saturated warm Eastmancolor palette, soft diffusion glow on highlights, hard studio key lighting, slightly faded blacks, and natural proportions.
[Shot 1] A medium close-up of <Subject 2>, front-facing, seated in the revolving chair of <Subject 3>, a red gel light behind him and drifting smoke. The camera holds a static shot. He smiles slowly without it reaching his eyes, rolling a cigar between his fingers. <Subject 2> (S1) says in a low, raspy male voice, half-whispered, with a slow, menacing drawl, the voice sounding studio-dubbed and slightly reverberant, <d>[Hindi] इंस्पेक्टर, यहाँ का क़ानून मैं हूँ.</d> He closes his lips and blows out smoke.
[Shot 2] At 00:04.000, the camera cuts to a medium shot of <Subject 1>, front-facing from a slightly low angle, standing in a pool of hard white key light with a blue gel rim behind him. His jaw is set and his eyes blaze. <Subject 1> (S2) declares in a smooth, resonant baritone male voice, speaking formal, theatrical Hindi, with a dramatic pause before the last word, <d>[Hindi] और उस क़ानून की मौत, मैं हूँ!</d> On the last word, the camera zooms in with large amplitude at fast speed onto a close-up of his face. He closes his lips and holds the stare.
[Shot 3] At 00:07.500, the camera cuts to a close-up of <Subject 2>, front-facing. The camera holds a static shot. His smile drains away, his eyes widen, and the cigar stops halfway to his lips.

overall_soundscape:
A low hum of the den's fan, drifting smoke hiss, and the creak of the revolving chair. A sharp whoosh accompanies the zoom.

non_diegetic_music:
Dramatic string-section stings with a crashing cymbal on the zoom, followed by a held low brass note at a slow tempo.
```

(`इंस्पेक्टर, यहाँ का क़ानून मैं हूँ.` = "Inspector, I am the law here." `और उस क़ानून की मौत, मैं हूँ!` = "And I am the death of that law!")

### T2VA: song-sequence romance in a mustard field (8 s, no dialogue)

Settings: 8 s, 2K, 16:9.

```text
integrated_multimodal_description: [Shot 1] Vintage film, 1980s Hindi masala-film look on grainy 35mm with saturated warm colors and soft diffusion glow, a medium shot at eye level frames a young Indian woman in a flowing chiffon saree in bright magenta, big hair with side curls, gold bangles, and bold eyeliner, standing in a vast yellow mustard field under a clear blue sky, facing a young man in a white open-collar shirt and flared trousers. Star-filter sparkles glint on her earrings. The camera arcs around them with small amplitude at slow speed. She spins once, her saree pallu lifting in the breeze, then stops facing him with a shy, closed-lip smile, glancing up through her lashes. He smiles back, his eyes soft. [Shot 2] At 00:04.500, the camera cuts to a close-up of the woman, front-facing, her face glowing in soft diffusion. The camera zooms in with small amplitude at slow speed. Her eyes linger on him, and she lowers her gaze and bites her lip with a shy smile as wind lifts a curl across her cheek.

overall_soundscape: Breeze rustling through the mustard plants, the soft swish of chiffon, and the jingle of her bangles as she spins.

non_diegetic_music: A romantic 1980s film-song arrangement with lush strings, a sitar melody, tabla, and a soft synth pad at a moderate tempo, swelling on the close-up.
```
