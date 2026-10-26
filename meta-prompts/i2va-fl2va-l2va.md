# H3 I2VA / FL2VA / L2VA — frame modes

Frame images cannot be combined with reference images, videos, or audio. Everyone
who must look exact has to already be in the frame image. Ratio always follows
the image (`adaptive`).

## Sub-modes

| Images | Sub-mode | Roles |
|---|---|---|
| 1, opening | I2VA | `first_frame` |
| 2, opening + ending | FL2VA | `first_frame` + `last_frame` |
| 1, ending | L2VA | `last_frame` |

## Instruction line (first line, verbatim, then one blank line)

- **I2VA**
  `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`
- **FL2VA**
  `How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot N) aligns with the S.SS-second mark of the target video.`
- **L2VA**
  `How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the S.SS-second mark of the target video.`

`N` is the index of the actual final shot; `S.SS` is the duration with exactly two
decimals (`8.00`). The FL2VA line has no angle or square brackets.

## Then the three fields

```text
integrated_multimodal_description: [Shot 1] Live-action, cinematic, the subject shown in <Picture 1> … (style, then what the frame shows, then the action)

overall_soundscape: …

non_diegetic_music: …
```

## Paths

- **I2VA:** first-frame anchor → action onset → continuous development → result.
- **FL2VA:** first-frame state → visible intermediate changes → last-frame state;
  prefer one shot so H3 interpolates continuously.
- **L2VA:** plausible earlier state → explicit action → convergence onto the last
  frame at the end.
- Do not cut to a framing the image cannot support.

<!-- version: 1 -->
