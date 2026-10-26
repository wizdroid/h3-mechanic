# 05 — Voice-timbre library

Use these when a character speaks and there is **no `<Audio N>` voice reference**. H3 builds a voice from the words placed **outside** `<d>`: age, gender, pitch, texture, pace and accent.

## How to use

1. Pick one ID per speaker and note it in your output (`S1 = M5, S2 = F6`).
2. At the speaker's **first** line, paste the full phrase:
   `… (S1) says in a hard, clipped mid-low male voice with a brisk staccato pace, <d>[Kannada] …</d>`
3. In later shots, reuse the short tag so the voice stays the same:
   `… (S1) replies in the same hard, clipped voice, <d>…</d>`
4. Add the delivery after the voice, not instead of it:
   `…says in a soft, breathy young female voice, barely above a whisper and trembling, <d>…</d>`
5. Add an accent clause when it matters (table at the end).
6. Two speakers in one scene need clearly different IDs (different gender, age band or pitch).
7. For T2VA/I2VA the subject is a description, not a label: `The middle-aged officer with a deep, gravelly voice (S1) says, …`

If an `<Audio N>` voice exists, it replaces the library phrase:
`…says in the voice timbre referenced from <Audio 1>, …`

## Female voices

| ID | Name | Age | Pitch | Texture | Pace | Roles | Paste phrase |
|---|---|---|---|---|---|---|---|
| F1 | Soft breathy | 18–25 | Mid-high | Airy, breathy, gentle | Slow | Shy lead, young bride, romantic heroine | `in a soft, breathy young female voice with a slow, gentle pace` |
| F2 | Bright clear | 20–30 | Mid-high | Clear, bright, crisp | Brisk | Confident heroine, student, reporter | `in a bright, clear young female voice with a lively, brisk pace` |
| F3 | Warm velvet | 28–40 | Mid | Warm, rounded, smooth | Moderate | Mother, doctor, narrator, kind sister | `in a warm, velvety female voice in her thirties with a calm, even pace` |
| F4 | Low husky | 25–40 | Low | Husky, slightly smoky | Unhurried | Rebel, femme fatale, hardened convict | `in a low, husky female voice with a slightly smoky texture and an unhurried pace` |
| F5 | Crisp authoritative | 35–50 | Mid-low | Firm, articulate, precise | Measured | Woman officer, lawyer, judge, boss | `in a crisp, authoritative mid-low female voice with precise diction and a measured pace` |
| F6 | Fragile trembling | 20–35 | Mid-high | Thin, slightly trembling, hushed | Hesitant | Guilty convict, victim, frightened witness | `in a thin, fragile young female voice with a slight tremble and a hesitant pace` |
| F7 | Rich matriarch | 50–65 | Low-mid | Rich, resonant, slightly gravelly | Deliberate | Mother-in-law, matriarch, female don | `in a rich, resonant older female voice with a slight gravel and a deliberate pace` |
| F8 | Elderly frail | 65–80 | Mid | Papery, cracked, soft | Slow, with pauses | Grandmother, old villager | `in a frail, cracked elderly female voice with a slow pace and small pauses` |
| F9 | Playful sassy | 16–24 | High | Bright, teasing, sing-song | Quick | Comic friend, younger sister, college girl | `in a playful, high, teasing young female voice with a quick, sing-song rhythm` |
| F10 | Sweet melodic | 20–28 | Mid-high | Sweet, smooth, honeyed, softly musical | Gentle, flowing | Female protagonist, heroine, innocent lead | `in a sweet, melodic young female voice, smooth and honeyed, with a gentle, flowing pace` |

## Male voices

| ID | Name | Age | Pitch | Texture | Pace | Roles | Paste phrase |
|---|---|---|---|---|---|---|---|
| M1 | Deep gravelly | 45–60 | Low | Gravelly, weathered | Slow, measured | Senior officer, don, father | `in a deep, gravelly middle-aged male voice with a slow, measured pace` |
| M2 | Resonant baritone | 30–45 | Low-mid | Smooth, resonant, full | Steady | Hero, lead officer, lawyer | `in a smooth, resonant baritone male voice with a steady, confident pace` |
| M3 | Warm gentle | 25–35 | Mid | Soft, warm, slightly husky | Relaxed | Romantic lead, kind brother, doctor | `in a warm, gentle young male voice with a soft husk and a relaxed pace` |
| M4 | Young energetic | 18–25 | Mid-high | Bright, light | Fast | College boy, sidekick, younger brother | `in a bright, energetic young male voice with a fast, eager pace` |
| M5 | Stern commanding | 35–50 | Mid-low | Hard, clipped, projected | Brisk staccato | Jail warden, inspector, army officer | `in a hard, clipped mid-low male voice with a brisk staccato pace` |
| M6 | Raspy menacing | 30–50 | Low | Raspy, half-whispered, dry | Slow drawl | Villain, henchman, blackmailer | `in a low, raspy male voice, half-whispered, with a slow, menacing drawl` |
| M7 | Nasal comic | 25–45 | Mid-high | Nasal, reedy | Quick, uneven | Comic constable, shopkeeper, side character | `in a reedy, slightly nasal male voice with a quick, uneven rhythm` |
| M8 | Elderly wise | 65–80 | Low-mid | Thin, cracked, warm | Slow | Grandfather, priest, retired judge | `in a thin, cracked elderly male voice, warm but tired, with a slow pace` |
| M9 | Nervous thin | 20–35 | Mid | Thin, tight, breathy | Rushed, stumbling | Accused man, clerk, informer | `in a thin, tight young male voice that rushes and stumbles over the words` |
| M10 | Soft-spoken calm | 25–40 | Mid-low | Soft, quiet, velvety, close to the mic | Slow, unhurried | Quiet hero, poet, gentle father, shy lover | `in a soft-spoken, quiet male voice, velvety and calm, with a slow, unhurried pace` |
| M11 | Deep villain bass | 35–55 | Very low | Deep bass, smooth, cold, resonant | Slow, deliberate, controlled | Main villain, crime boss, corrupt politician | `in a very deep, cold bass male voice, smooth and resonant, with a slow, deliberate, menacing calm` |

## Children (optional)

| ID | Phrase |
|---|---|
| K1 girl 6–10 | `in a small, high, clear little girl's voice` |
| K2 boy 6–10 | `in a small, bright little boy's voice with an excited pace` |

## Accent and language clauses

Append after the voice phrase. Use them only when they change the performance.

| Clause | Use |
|---|---|
| `with a light Indian English accent` | English lines by Indian characters |
| `speaking Kannada with a natural Bengaluru urban accent` | City Kannada, mixes English words easily |
| `speaking Kannada with a rustic North Karnataka accent` | Village characters, Dharwad / Hubballi region |
| `speaking Kannada with a soft Mysuru accent` | Old-Mysuru region, polite register |
| `speaking Hindi with a Mumbai street accent` | Tapori / Bambaiya characters |
| `speaking formal, theatrical Hindi` | 80s Bollywood heroes, villains, judges |
| `speaking Tamil with a Chennai accent` | Tamil characters |
| `speaking Telugu with a Hyderabad accent` | Telugu characters |
| `speaking Malayalam with a soft Kerala lilt` | Malayalam characters |
| `with a neutral American accent` / `with a British accent` | Non-Indian roles |

## Suggested pairings for the prison drama

| Role | Voice |
|---|---|
| Male officer giving orders | M5 (or M1 if senior) |
| Female convict, guilty | F6; F4 if she is hardened |
| Woman officer / warden | F5 |
| Kind older inmate | F7 or F8 |
| Constable comic relief | M7 |
