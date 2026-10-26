# 01 — Modes and hard limits

## Pick the mode

| What you have | Mode | Skill / sheet |
|---|---|---|
| Text only | **T2VA** | [08-t2va.md](08-t2va.md) |
| One image that must be the exact opening frame | **I2VA** | [09-i2va-fl2va-l2va.md](09-i2va-fl2va-l2va.md) |
| Two images that must be the exact first **and** last frames | **FL2VA** | [09-i2va-fl2va-l2va.md](09-i2va-fl2va-l2va.md) |
| One image that must be the exact final frame | **L2VA** | [09-i2va-fl2va-l2va.md](09-i2va-fl2va-l2va.md) |
| Character / location / prop / motion / voice references that are **not** the literal frame | **Ref2VA** | [10-ref2va.md](10-ref2va.md) |

### Mode policy defaults

- **Default to I2VA** (faster). Switch to Ref2VA only when I2VA would break identity: a face that matters is hidden / turned / out of frame, an unlisted person appears, the camera reveals a new side, or an audio/motion reference is required.
- **Never mix reference roles with first/last frame roles.** `reference_image`, `reference_video`, `reference_audio` and `first_frame` / `last_frame` cannot be in the same request.
- **I2VA cannot take extra character images.** Every person who must look exact has to already be in the first frame.
- If the user wants both character references **and** an exact opening frame: build the opening frame first (Qwen edit / Krea 2) and run I2VA, **or** use Ref2VA with the location image as a composition anchor (`<Picture N>` standalone).

## MiniMax API hard limits (`/v2/video_generation`)

### Model limits

| Model | Duration | Resolution |
|---|---|---|
| `MiniMax-H3` | integer **4–15 s** | `768P` or `2K` |
| `MiniMax-H3-Max` | **5–15 s** | `480P` / `768P` (no 2K) |

### Ratio

| Mode | Ratio |
|---|---|
| T2VA | **Concrete ratio required** — `21:9`, `16:9`, `4:3`, `1:1`, `3:4`, `9:16`. Never `adaptive`. |
| I2VA / FL2VA / L2VA | Always follows the image (`adaptive`) |
| Ref2VA | `adaptive` by default, or a concrete ratio |

### Ref2VA input budget

- ≤ **9 images**
- ≤ **3 videos**
- ≤ **3 audio clips**
- Each audio/video clip **2–15 s**, total ≤ 15 s per type
- ≤ **12 files overall**

### Image limits

- **256–5760 px** per side
- Width/height ratio **0.4–2.5**

### Text limit

- Prompt text ≤ **7000 characters**.
- A six-section Ref2VA prompt with a ~500-word description fits; re-check the length when dialogue is long.
