---
name: wechat-cover-skill
description: Generate WeChat Official Account cover images from a title, thesis, article summary, or PPT topic. Use when the user asks for 公众号封面图, 公众号头图, 微信 21:9 配图, 微信分享卡, or wants only the cover-image part of a larger content pipeline without generating a PPT.
---

# WeChat Cover Skill

Use this skill when the job is only cover-image generation. Do not branch into PPT layout, HTML deck generation, or slide validation unless the user explicitly asks for that too.

## Minimal input

Try to normalize the request into:

- `title`
- `subtitle` or one-line thesis
- `style`
- `accent`
- `variant`

If the user provides source text instead of structured inputs, distill them yourself. In Codex, ask at most 1-2 short questions only when the missing input would materially change the image.

Default assumptions:

- style = `swiss`
- accent = `ikb`
- variant = `wechat-21x9`
- language follows the source language

### Allowed values

| Field | Allowed values | Default |
|---|---|---|
| `style` | `swiss`, `editorial` | `swiss` |
| `accent` | `ikb`, `lemon-yellow`, `lemon-green`, `safety-orange`, `none` | `ikb` |
| `variant` | `wechat-21x9`, `wechat-share-1x1` | `wechat-21x9` |

Use `accent = none` when `style = editorial`.

### Accent guide

- `ikb`: safest default for AI, tech, methods, analysis, product, design
- `lemon-yellow`: youthful, retail, energetic, pop
- `lemon-green`: future, ecology, emerging tech, younger tone
- `safety-orange`: alert, urgency, industrial, strong emphasis

`editorial` style does not need a Swiss accent preset and should stay more restrained.

## Workflow

1. If the source is long, extract one headline, one subtitle, and 3-5 keywords.
2. Read [`references/cover-spec.md`](references/cover-spec.md) for the payload contract, output variants, and prompt templates.
3. Pick one visual system only. Do not mix Swiss and editorial rules in one image.
4. Generate the image with the native image tool.
5. Prioritize title readability and cover impact over decorative detail.
6. If the user wants reusable pipeline material, also return the final prompt text and the normalized payload.

## Guardrails

- The cover image is a platform asset, not a slide.
- Do not generate PPT page chrome, slide numbers, fake browser frames, or watermark-like corner labels.
- Keep copy short. Title first, subtitle optional, no body text blocks.
- Use only one accent color.
- Avoid gradients, soft shadows, rounded cards, glassmorphism, neon, or generic SaaS hero aesthetics.
- For Swiss style, prefer strict alignment, rectilinear blocks, strong whitespace, and sans-serif typography.
- For editorial style, prefer restrained texture, warmth, and human atmosphere without turning into advertising gloss.
- Do not mix `editorial` style with Swiss accent semantics. If `style = editorial`, prefer `accent = none`.

## Pipeline handoff

For machine-driven pipelines, read:

- [`references/cover-spec.md`](references/cover-spec.md) for field semantics and prompt templates
- [`references/payload-schema.json`](references/payload-schema.json) for validation
- [`references/payload-examples.json`](references/payload-examples.json) for ready-made examples
- [`scripts/build-prompt.mjs`](scripts/build-prompt.mjs) to turn payload JSON into a final prompt

## Output behavior

- Default: return the image only.
- If asked for a prompt or pipeline integration, return:
  - the normalized payload
  - the final prompt text
  - any assumptions you filled in
