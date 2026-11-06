# 07 — Dialogue languages and on-screen text

The H3 guides require the whole prompt in English, **except** dialogue/lyrics inside `<d>` and text visibly present in the scene. Those keep their original language and are never translated or rewritten.

## Dialogue tag

```text
<d>[Language] exact words.</d>
```

- Use the English name of the language in the tag: `[English]`, `[Kannada]`, `[Hindi]`, `[Tamil]`, `[Telugu]`, `[Malayalam]`, `[Marathi]`, `[Bengali]`.
- Write the line in its **native script**. H3's tokenizer reads native script more reliably than romanised spelling.
- When the user gives a romanised line (`wolage hogu`), convert it to native script, show both in chat for confirmation (`ಒಳಗೆ ಹೋಗು` = "olage hogu", "go inside"), and put only the native script in `<d>`.
- End the line with `.`, `?` or `!`. Use `.` rather than the Devanagari danda `।`.
- One language per `<d>` block. For code-mixed speech (Kanglish, Hinglish), tag the dominant language and keep English words in Latin script exactly as spoken: `<d>[Kannada] ಏನ್ ಮಾಡ್ತಿದ್ದೀಯಾ, sir?</d>`. If two full sentences are in two languages, use two `<d>` blocks.
- Voice, accent and delivery go outside `<d>` (see [05-voice-library.md](05-voice-library.md)).

## Ready lines (check with the user before use)

| Meaning | Kannada | Hindi | Tamil | Telugu | Malayalam |
|---|---|---|---|---|---|
| Go inside. | ಒಳಗೆ ಹೋಗು. | अंदर जाओ. | உள்ளே போ. | లోపలికి వెళ్ళు. | അകത്തേക്ക് പോ. |
| Come here. | ಇಲ್ಲಿ ಬಾ. | इधर आओ. | இங்கே வா. | ఇక్కడికి రా. | ഇവിടെ വാ. |
| Stop! | ನಿಲ್ಲು! | रुको! | நில்! | ఆగు! | നിൽക്ക്! |
| Tell the truth. | ಸತ್ಯ ಹೇಳು. | सच बताओ. | உண்மையைச் சொல். | నిజం చెప్పు. | സത്യം പറ. |
| Forgive me. | ನನ್ನನ್ನು ಕ್ಷಮಿಸಿ. | मुझे माफ़ कर दो. | என்னை மன்னித்துவிடு. | నన్ను క్షమించు. | എന്നോട് ക്ഷമിക്കൂ. |
| I didn't do anything. | ನಾನು ಏನೂ ಮಾಡಿಲ್ಲ. | मैंने कुछ नहीं किया. | நான் எதுவும் செய்யவில்லை. | నేను ఏమీ చేయలేదు. | ഞാൻ ഒന്നും ചെയ്തിട്ടില്ല. |
| Keep quiet. | ಸುಮ್ಮನಿರು. | चुप रहो. | பேசாமல் இரு. | నోరు మూసుకో. | മിണ്ടാതിരിക്ക്. |

Kannada register: `ಹೋಗು` / `ಬಾ` is the familiar/commanding form an officer uses with a prisoner. Polite forms are `ಹೋಗಿ` / `ಬನ್ನಿ`. Choose the register that fits who is speaking to whom.

## On-screen text

Put visible signs, labels and captions in English double quotes, verbatim and in their own script:

```text
Above the gate, a weathered metal board reads "ಕೇಂದ್ರ ಕಾರಾಗೃಹ" in white Kannada letters.
```

- Keep signs short (one to three words). Long signs render as gibberish.
- If a sign is not important, describe it without readable text (`a faded government notice board`).

## Subtitles

Do **not** ask H3 for subtitles. Add them in the edit, where they can be corrected.
