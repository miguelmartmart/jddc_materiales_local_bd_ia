/**
 * nextActionParser.ts
 * -------------------
 * Pure utility: parse [[NEXT_ACTION:{...}]] blocks from AI message content.
 *
 * No React, no Electron, no side effects.
 * Importable by any project that uses the same [[NEXT_ACTION]] convention.
 *
 * Robustness layers (applied in order until one succeeds):
 *   1. Parse raw JSON as-is.
 *   2. Extract only the first balanced JSON object (handles trailing text after `}`).
 *   3. Fix unescaped Windows backslashes in string values, then parse.
 */

export interface NextAction {
  type: string;
  content: string;
  label?: string;
  cancel_label?: string;
  cancel_message?: string;
  [key: string]: unknown;
}

export interface ParseResult {
  action: NextAction | null;
  /** Non-null when a [[NEXT_ACTION]] block exists but its JSON is malformed. */
  error: string | null;
}

const NEXT_ACTION_REGEX = /\[\[\s*NEXT_ACTION\s*:\s*([\s\S]*?)\]\]/i;

/**
 * Walk a string character-by-character and return the substring that forms
 * the first complete, balanced JSON object `{...}`.
 * Returns null if no balanced object is found.
 */
function extractFirstJsonObject(str: string): string | null {
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = 0; i < str.length; i++) {
    const ch = str[i];

    if (escaped) {
      escaped = false;
      continue;
    }
    if (ch === '\\' && inString) {
      escaped = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;

    if (ch === '{') {
      depth++;
    } else if (ch === '}') {
      depth--;
      if (depth === 0) {
        return str.slice(0, i + 1);
      }
    }
  }
  return null;
}

/**
 * Escape backslashes that are not part of a valid JSON escape sequence.
 * Handles Windows paths like C:\Users\foo → C:\\Users\\foo inside JSON strings.
 */
function fixBackslashes(str: string): string {
  // Replace \ not followed by " \ / b f n r t u with \\
  return str.replace(/\\(?!["\\\/bfnrtu])/g, '\\\\');
}

/**
 * Extract and parse the first [[NEXT_ACTION:{...}]] block from a message.
 * Returns { action: null, error: null } when no block is found.
 * Returns { action: null, error: string } when a block exists but is malformed.
 */
export function parseNextAction(rawContent: string): ParseResult {
  const match = rawContent.match(NEXT_ACTION_REGEX);
  if (!match) return { action: null, error: null };

  const rawJson = match[1]
    .trim()
    .replace(/^```json\s*/, '')
    .replace(/^```\s*/, '')
    .replace(/\s*```$/, '')
    .replace(/\n/g, ' ');

  // Layer 1: parse as-is
  try {
    return { action: JSON.parse(rawJson) as NextAction, error: null };
  } catch (_) { /* fall through */ }

  // Layer 2: extract the first balanced { } object — handles trailing text after JSON
  try {
    const balanced = extractFirstJsonObject(rawJson);
    if (balanced) {
      return { action: JSON.parse(balanced) as NextAction, error: null };
    }
  } catch (_) { /* fall through */ }

  // Layer 3: fix unescaped backslashes then retry balanced extraction
  try {
    const fixed = fixBackslashes(rawJson);
    const balanced = extractFirstJsonObject(fixed);
    if (balanced) {
      return { action: JSON.parse(balanced) as NextAction, error: null };
    }
    return { action: JSON.parse(fixed) as NextAction, error: null };
  } catch (_) { /* fall through */ }

  // All layers exhausted
  return {
    action: null,
    error: 'No se pudo interpretar la acción generada por la IA. Inténtalo de nuevo.',
  };
}

/** Action types that produce visible buttons in the UI. */
const EXECUTABLE_TYPES = new Set([
  'run_command',
  'browser',
  'confirm_plan',
  'open_file',
  'chat_message',
]);

export function isExecutableAction(action: NextAction | null): boolean {
  return !!action && EXECUTABLE_TYPES.has(action.type);
}

/** Return the raw [[NEXT_ACTION]] substring if present, for stripping or logging. */
export function extractRawNextAction(rawContent: string): string | null {
  const match = rawContent.match(NEXT_ACTION_REGEX);
  return match ? match[0] : null;
}
