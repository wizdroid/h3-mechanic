# 16 — Pre-flight checklist

Run this before returning any H3 prompt.

1. **Mode and field names** match the mode template exactly.
   - T2VA → `integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music`
   - I2VA / FL2VA / L2VA → instruction line, then the same three fields
   - Ref2VA → the six sections in order: `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`
2. **Every label used is defined once and keeps its meaning** (Ref2VA).
3. **Cut times** are strictly increasing and below the duration; shot count fits the duration. `[Shot 1]` has no timestamp.
4. **Each shot has one camera move**, worded with an official verb, with a landing (`toward…`, `revealing…`, `as…`).
5. **Every speaking or readable face** is close-up, medium close-up or medium, front or three-quarter; any wide shot is from behind, an establishing view, or has no readable faces.
6. **Every speaker** has an `(Sx)`, a voice phrase at first appearance (library ID or `<Audio N>`), and the same voice wording in later shots.
7. **Dialogue** is verbatim, in native script, inside `<d>[Language] …</d>`.
8. **Soundscape and music** follow the shared grammar. Prompt ≤ 7000 characters.

## Output format (to the user)

Return the prompt in one ```text fence, then a short block: mode, duration, resolution, ratio, attach order (which file is image 1, 2…), and the voice IDs used. Offer at most two variations (for example a safer framing).

## Ref2VA-specific additions

- Summary prefix is one task type or several joined with ` + `, never repeated.
- Retention markers are correct (visual: `fully_preserved` / `partially_preserved` / `attribute_transfer` / `weak_reference`; audio: `fully_copy` / `partially_copy` / `reference` / `weak_reference`).
- No `(Sx)` in `retention_analysis`.
- Style sentence(s) come **before** `[Shot 1]` and start `The target video is …`.
- Budget: ≤ 9 images, ≤ 3 videos, ≤ 3 audio, ≤ 12 files.
