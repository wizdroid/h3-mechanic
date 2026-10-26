# H3 T2VA — text-to-video-with-audio

Text only, no references. Use a concrete ratio (21:9, 16:9, 4:3, 1:1, 3:4, 9:16);
`adaptive` is rejected. Default 8–10 s and 16:9 when unstated.

## Format

No instruction line. Three fields, each `field_name: content` on one line, a
blank line between fields:

```text
integrated_multimodal_description: [Shot 1] Live-action, cinematic, <opening composition>, <subjects and positions>, <environment and light>. <One camera move>. <Action, expressions, sounds>. The <voice description> (S1) says, <d>[Language] …</d> [Shot 2] At 00:05.000, the camera cuts to …

overall_soundscape: …

non_diegetic_music: …
```

- `integrated_multimodal_description` is one continuous paragraph; shots follow
  each other inline.
- Describe each character once, clearly, at first appearance; keep the same short
  handle afterwards. In T2VA the speaker is a description, not a label:
  `The stern officer with a deep, gravelly voice (S1) orders, <d>…</d>`.

<!-- version: 1 -->
