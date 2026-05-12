#!/usr/bin/env node

import { readFileSync } from 'node:fs';

const STYLE_ENUM = new Set(['swiss', 'editorial']);
const ACCENT_ENUM = new Set(['ikb', 'lemon-yellow', 'lemon-green', 'safety-orange', 'none']);
const VARIANT_ENUM = new Set(['wechat-21x9', 'wechat-share-1x1']);

const ACCENT_LABELS = {
  ikb: 'IKB blue',
  'lemon-yellow': 'lemon yellow',
  'lemon-green': 'lemon green',
  'safety-orange': 'safety orange',
  none: 'none',
};

const args = process.argv.slice(2);
const promptOnly = args.includes('--prompt-only');
const compact = args.includes('--compact');
const help = args.includes('--help') || args.includes('-h');
const inputArg = args.find((arg) => !arg.startsWith('--'));

if (help) {
  process.stdout.write(
    [
      'Usage:',
      '  node scripts/build-prompt.mjs <payload.json>',
      '  cat payload.json | node scripts/build-prompt.mjs',
      '',
      'Options:',
      '  --prompt-only   Output only the final prompt text',
      '  --compact       Output compact JSON instead of pretty JSON',
    ].join('\n'),
  );
  process.exit(0);
}

const rawInput = readInput(inputArg);
const parsed = parsePayload(rawInput);
const { normalized, assumptions } = normalizePayload(parsed);
const templateId = `${normalized.style}.${normalized.variant}`;
const finalPrompt = buildPrompt(normalized);

if (promptOnly) {
  process.stdout.write(finalPrompt);
  process.exit(0);
}

const result = {
  normalized_payload: normalized,
  template_id: templateId,
  final_prompt: finalPrompt,
  assumptions,
};

process.stdout.write(JSON.stringify(result, null, compact ? 0 : 2));

function readInput(pathArg) {
  if (pathArg) return readFileSync(pathArg, 'utf8');
  if (process.stdin.isTTY) {
    throw new Error('No input provided. Pass a JSON file path or pipe JSON via stdin.');
  }
  return readFileSync(0, 'utf8');
}

function parsePayload(text) {
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`Invalid JSON input: ${error.message}`);
  }
}

function normalizePayload(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('Payload must be a JSON object.');
  }

  const assumptions = [];
  const normalized = {};

  normalized.title = cleanString(input.title);
  if (!normalized.title) {
    throw new Error('`title` is required.');
  }

  normalized.subtitle = cleanString(input.subtitle);
  if (!normalized.subtitle) {
    delete normalized.subtitle;
  }

  normalized.style = normalizeStyle(input.style, assumptions);
  normalized.variant = normalizeVariant(input.variant, assumptions);
  normalized.language = normalizeLanguage(input.language, normalized.title, assumptions);
  normalized.accent = normalizeAccent(input.accent, normalized.style, assumptions);
  normalized.keywords = normalizeKeywords(input.keywords, normalized.title, normalized.subtitle, assumptions);

  return { normalized, assumptions };
}

function normalizeStyle(style, assumptions) {
  const value = cleanString(style)?.toLowerCase();
  if (!value) {
    assumptions.push('style defaulted to swiss');
    return 'swiss';
  }
  if (!STYLE_ENUM.has(value)) {
    throw new Error(`Unsupported style: ${style}`);
  }
  return value;
}

function normalizeVariant(variant, assumptions) {
  const value = cleanString(variant)?.toLowerCase();
  if (!value) {
    assumptions.push('variant defaulted to wechat-21x9');
    return 'wechat-21x9';
  }
  if (!VARIANT_ENUM.has(value)) {
    throw new Error(`Unsupported variant: ${variant}`);
  }
  return value;
}

function normalizeLanguage(language, title, assumptions) {
  const value = cleanString(language);
  if (value) return value;

  const inferred = /[\u3400-\u9fff]/.test(title) ? 'zh-CN' : 'en-US';
  assumptions.push(`language defaulted to ${inferred}`);
  return inferred;
}

function normalizeAccent(accent, style, assumptions) {
  const rawValue = cleanString(accent)?.toLowerCase();
  const value = rawValue || null;

  if (!value) {
    const fallback = style === 'editorial' ? 'none' : 'ikb';
    assumptions.push(`accent defaulted to ${fallback}`);
    return fallback;
  }

  if (!ACCENT_ENUM.has(value)) {
    throw new Error(`Unsupported accent: ${accent}`);
  }

  if (style === 'editorial' && value !== 'none') {
    assumptions.push(`accent coerced from ${value} to none for editorial style`);
    return 'none';
  }

  if (style === 'swiss' && value === 'none') {
    assumptions.push('accent coerced from none to ikb for swiss style');
    return 'ikb';
  }

  return value;
}

function normalizeKeywords(keywords, title, subtitle, assumptions) {
  if (Array.isArray(keywords)) {
    const cleaned = keywords
      .map((item) => cleanString(item))
      .filter(Boolean)
      .slice(0, 8);
    if (cleaned.length) return cleaned;
  }

  const derived = deriveKeywords(title, subtitle);
  assumptions.push('keywords derived from title and subtitle');
  return derived;
}

function deriveKeywords(title, subtitle) {
  const segments = [title, subtitle]
    .filter(Boolean)
    .flatMap((value) => splitSegments(value))
    .map((value) => value.trim())
    .filter(Boolean);

  const unique = [];
  const seen = new Set();
  for (const segment of segments) {
    if (!seen.has(segment)) {
      seen.add(segment);
      unique.push(segment);
    }
    if (unique.length >= 5) break;
  }

  return unique.length ? unique : [title];
}

function splitSegments(value) {
  return value
    .split(/[，,。.!！?？；;：:\n、/|]/g)
    .map((part) => part.trim())
    .filter(Boolean)
    .flatMap((part) => {
      if (/[\u3400-\u9fff]/.test(part) || !/\s/.test(part)) return [part];
      return part.split(/\s+/g).filter(Boolean);
    });
}

function buildPrompt(payload) {
  const visualKeywords = payload.keywords.join(', ');
  const accentText = ACCENT_LABELS[payload.accent];

  if (payload.style === 'swiss' && payload.variant === 'wechat-21x9') {
    return joinSentences([
      '21:9 ultra-wide WeChat official account cover image.',
      `Swiss International Typographic Style, black white gray with a single ${accentText} accent, strict grid feeling, asymmetrical composition, strong negative space, sharp rectangular blocks, hairline rules, clean sans-serif typography.`,
      `Headline text prominently integrated: "${payload.title}".`,
      payload.subtitle ? `Smaller subtitle text: "${payload.subtitle}".` : null,
      `Visual should suggest ${visualKeywords} in a minimal, elegant way.`,
      'Prioritize title readability and cover impact.',
      'No gradients, no shadows, no rounded corners, no fake app UI, no page chrome, no logo, no watermark, no clutter.',
    ]);
  }

  if (payload.style === 'swiss' && payload.variant === 'wechat-share-1x1') {
    return joinSentences([
      'Square 1:1 WeChat share card.',
      `Swiss International Typographic Style, black white gray with a single ${accentText} accent, bold title block, clean sans-serif typography, strong grid, large negative space, minimal geometric support elements.`,
      `Headline text prominently integrated: "${payload.title}".`,
      payload.subtitle ? `Optional smaller subtitle: "${payload.subtitle}".` : null,
      `Visual should suggest ${visualKeywords} in a minimal, elegant way.`,
      'Prioritize small-size readability.',
      'No gradients, no shadows, no rounded corners, no logo, no watermark, no page chrome.',
    ]);
  }

  if (payload.style === 'editorial' && payload.variant === 'wechat-21x9') {
    return joinSentences([
      '21:9 ultra-wide WeChat official account cover image.',
      'Editorial magazine cover feeling, restrained composition, tactile texture, documentary or conceptual visual, generous whitespace, elegant typography, calm and intelligent mood.',
      `Headline text prominently integrated: "${payload.title}".`,
      payload.subtitle ? `Smaller subtitle text: "${payload.subtitle}".` : null,
      `Visual should suggest ${visualKeywords}.`,
      'Prioritize readability and a strong single focal point.',
      'No logo, no watermark, no fake page frame, no extra labels, no clutter, no glossy advertising style.',
    ]);
  }

  if (payload.style === 'editorial' && payload.variant === 'wechat-share-1x1') {
    return joinSentences([
      'Square 1:1 WeChat share card.',
      'Editorial magazine cover feeling, restrained composition, tactile texture, calm and intelligent mood, generous whitespace, elegant typography, one clear focal point.',
      `Headline text prominently integrated: "${payload.title}".`,
      payload.subtitle ? `Optional smaller subtitle: "${payload.subtitle}".` : null,
      `Visual should suggest ${visualKeywords}.`,
      'Prioritize small-size readability.',
      'No logo, no watermark, no fake page frame, no extra labels, no clutter, no glossy advertising style.',
    ]);
  }

  throw new Error(`No prompt template for ${payload.style} + ${payload.variant}`);
}

function joinSentences(parts) {
  return parts.filter(Boolean).join(' ');
}

function cleanString(value) {
  return typeof value === 'string' ? value.trim() : '';
}
