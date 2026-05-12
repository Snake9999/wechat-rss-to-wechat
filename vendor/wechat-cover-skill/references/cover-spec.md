# Cover Spec

Use this file when the task is to generate a portable WeChat cover-image request or feed the result into another pipeline.

## Normalized payload

Normalize incoming requests to this shape:

```json
{
  "title": "个人知识系统",
  "subtitle": "把输入、理解、连接与输出组织成一台可以反复调用的个人操作系统",
  "keywords": ["知识管理", "系统", "连接", "输出"],
  "style": "swiss",
  "accent": "ikb",
  "variant": "wechat-21x9",
  "language": "zh-CN"
}
```

Validate this shape with [`payload-schema.json`](payload-schema.json).

### Field notes

- `title`: required; ideally 4-12 Chinese characters or 2-6 English words
- `subtitle`: optional but recommended; keep it to one sentence
- `keywords`: optional; used to stabilize visual metaphors
- `style`: `swiss` or `editorial`
- `accent`: for Swiss use `ikb`, `lemon-yellow`, `lemon-green`, or `safety-orange`; for editorial use `none`
- `variant`: `wechat-21x9` or `wechat-share-1x1`
- `language`: keep typography and copy consistent with the source language

## Enum contract

| Field | Enum values | Notes |
|---|---|---|
| `style` | `swiss`, `editorial` | pick one visual system only |
| `accent` | `ikb`, `lemon-yellow`, `lemon-green`, `safety-orange`, `none` | `none` is preferred for editorial |
| `variant` | `wechat-21x9`, `wechat-share-1x1` | can be extended later if needed |
| `language` | free string, e.g. `zh-CN`, `en-US` | use source-language typography |

## Output variants

### `wechat-21x9`

- Primary use: 公众号头图
- Ratio: 21:9
- Goal: strong headline readability, one visual anchor, wide negative space
- Layout bias: title on the left or centered-left; anchor object or geometric weight on the right or edge

### `wechat-share-1x1`

- Primary use: 公众号分享卡
- Ratio: 1:1
- Goal: title readability in small previews
- Layout bias: larger title block, simplified secondary copy, stronger central composition

## Style rules

### Swiss

- Visual anchor: Swiss International Typographic Style
- Typography: clean sans-serif, hard alignment, strong hierarchy
- Color: black, white, gray, and one accent only
- Geometry: rectilinear blocks, hairline rules, no rounded corners
- Avoid: gradients, shadows, glass, neon, 3D, fake logos, fake app chrome

### Editorial

- Visual anchor: independent magazine cover or editorial poster
- Typography: elegant but restrained
- Color: muted, tactile, warm-neutral, low gloss
- Imagery: documentary or abstract conceptual scenes with breathing room
- Avoid: ad-like marketing renders, glossy stock-photo polish, over-designed overlays

## Prompt assembly

Build prompts from four parts:

1. Platform and ratio
2. Visual system
3. Title and subtitle
4. Hard negative constraints

Keep prompts compact. Do not write long cinematography essays.

## Prompt templates

### Swiss · `wechat-21x9`

```text
21:9 ultra-wide WeChat official account cover image. Swiss International Typographic Style, black white gray with a single [ACCENT] accent, strict grid feeling, asymmetrical composition, strong negative space, sharp rectangular blocks, hairline rules, clean sans-serif typography. Chinese headline text prominently integrated: "[TITLE]". Smaller subtitle text: "[SUBTITLE]". Visual should suggest [KEYWORDS] in a minimal, elegant way. Prioritize title readability and cover impact. No gradients, no shadows, no rounded corners, no fake app UI, no page chrome, no logo, no watermark, no clutter.
```

### Editorial · `wechat-21x9`

```text
21:9 ultra-wide WeChat official account cover image. Editorial magazine cover feeling, restrained composition, tactile texture, documentary or conceptual visual tied to [KEYWORDS], generous whitespace, elegant typography, calm and intelligent mood. Chinese headline text prominently integrated: "[TITLE]". Smaller subtitle text: "[SUBTITLE]". Prioritize readability and a strong single focal point. No logo, no watermark, no fake page frame, no extra labels, no clutter, no glossy advertising style.
```

### Editorial · `wechat-share-1x1`

```text
Square 1:1 WeChat share card. Editorial magazine cover feeling, restrained composition, tactile texture, calm and intelligent mood, generous whitespace, elegant typography, one clear focal point. Chinese headline text prominently integrated: "[TITLE]". Optional smaller subtitle: "[SUBTITLE]". Prioritize small-size readability. No logo, no watermark, no fake page frame, no extra labels, no clutter, no glossy advertising style.
```

### Swiss · `wechat-share-1x1`

```text
Square 1:1 WeChat share card. Swiss International Typographic Style, black white gray with a single [ACCENT] accent, bold title block, clean sans-serif typography, strong grid, large negative space, minimal geometric support elements. Chinese headline text prominently integrated: "[TITLE]". Optional smaller subtitle: "[SUBTITLE]". Prioritize small-size readability. No gradients, no shadows, no rounded corners, no logo, no watermark, no page chrome.
```

## Fallback rules

- If no subtitle is available, omit it instead of inventing a long explanatory line.
- If the title is too long, compress it before generating the image.
- If the request sounds methodical, technical, product-like, or presentation-adjacent, default to `swiss`.
- If the request sounds human, cultural, reflective, or essay-like, default to `editorial`.
- If `style = editorial` and the caller sends a Swiss accent value, ignore it or coerce it to `none`.

## Pipeline use

For another pipeline, the safest sequence is:

1. Normalize upstream content into the payload shape above.
2. Validate against `payload-schema.json`.
3. Run `scripts/build-prompt.mjs` to normalize and assemble the final prompt.
4. Send the final prompt to your image model.
5. Store the payload and final prompt together for reproducibility.

### Script usage

```bash
node scripts/build-prompt.mjs references/payload-example.json
```

Prompt only:

```bash
node scripts/build-prompt.mjs references/payload-example.json --prompt-only
```

Read from stdin:

```bash
cat references/payload-example.json | node scripts/build-prompt.mjs
```

## Suggested coercion rules

Use these when upstream content is messy:

- Missing `style` -> `swiss`
- Missing `accent` with `style = swiss` -> `ikb`
- Missing `accent` with `style = editorial` -> `none`
- Missing `variant` -> `wechat-21x9`
- Empty `keywords` -> derive 3-5 short concepts from title and subtitle
- Overlong `title` -> compress before generation rather than shrinking endlessly in the prompt
- Empty `subtitle` -> omit instead of fabricating a dense sentence
