# H3 Ref2VA — full-reference mode

Six sections in this exact order, each header on its own line, a blank line
between sections: `subject_definitions`, `summary`, `retention_analysis`,
`detailed_description`, `overall_soundscape`, `non_diegetic_music`.

## subject_definitions

```text
<Subject 1> is the … in <Picture 1>, …
<Picture 3> is the composition anchor for [Shot 1], defining …
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
```

## summary

One short paragraph using only the defined labels, prefixed by a task-type tag
(join several with ` + `): `reference generation`, `keyframe completion`,
`video editing`, `video continuation`, `audio reuse`, `audio reference`.

## retention_analysis

- Visual markers: `fully_preserved`, `partially_preserved`, `attribute_transfer`,
  `weak_reference`. Audio markers: `fully_copy`, `partially_copy`, `reference`,
  `weak_reference`. Never write `(Sx)` here.
- Entry shapes:
  `<Subject N> (appears in [Shot 1], [Shot 2]): marker - …`
  `<Picture N> ([Shot 1] composition anchor): marker - …`
  `<Video N> (camera path): marker - …`
  `<Audio N>: marker - …`

## detailed_description

- Opens with a one-or-two-sentence style line starting `The target video is …`,
  before `[Shot 1]`.
- `[Shot 1]` has no timestamp; later shots start
  `[Shot N] At MM:SS.mmm, the shot cuts to …`.
- One camera move per shot; frame anchors render as
  `the shot begins from <Picture 1>` / `the shot's keyframe corresponds to
  <Picture 2>` / `the shot ends on <Picture 3>`.
- Speaking subjects are `<Subject N> (Sx)` at first clear appearance.

## Audio policy

Default: `overall_soundscape: N/A`, `non_diegetic_music: N/A`, no sound
descriptions; end the style line with the dialogue-only closing sentence.

<!-- version: 1 -->
