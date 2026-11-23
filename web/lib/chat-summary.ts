/** One line of an answer's "Kurz gesagt" block: `- **Label**: text`. */
export type SummaryPoint = { label: string; text: string };

export type SplitAnswer = {
  /** Null when the answer has no "Kurz gesagt" block. */
  summary: SummaryPoint[] | null;
  /** The answer without the block. */
  body: string;
};

const HEADING = '**Kurz gesagt:**';
const BLOCK =
  /^\s*\*\*Kurz gesagt:?\*\*:?[ \t]*\n+((?:[ \t]*[-*][ \t][^\n]*(?:\n|$))*)/;
const POINT = /^[ \t]*[-*][ \t]+\*\*(.+?)\*\*\s*:?\s*(.*)$/;
// A source reference such as `[1]` or `[0, 2]`, or bold inside a point's
// text: a point is plain text after its label.
const STRAY = /\s*\[\d+(?:\s*,\s*\d+)*]|\*\*/g;

/** A bold label as the model writes it, `Grüne` or `Grüne:`. */
export function cleanLabel(label: string): string {
  return label.trim().replace(/:$/, '').trim();
}

/** Splits a leading "Kurz gesagt" block off an answer. A stream that has
 * only reached part of the heading shows nothing yet; a block with a line
 * that is not a labelled point stays in the text as written. */
export function splitSummary(markdown: string): SplitAnswer {
  const start = markdown.trimStart();
  if (start.length < HEADING.length && HEADING.startsWith(start) && start) {
    return { summary: [], body: '' };
  }
  const match = BLOCK.exec(markdown);
  if (!match) {
    return { summary: null, body: markdown };
  }
  // The stream may still be inside the block's last line.
  const streaming =
    match[0].length === markdown.length && !match[1].endsWith('\n');
  const lines = match[1].split('\n').filter((line) => line.trim());
  const points: SummaryPoint[] = [];
  for (const [index, line] of lines.entries()) {
    const point = POINT.exec(line);
    if (point) {
      points.push({
        label: cleanLabel(point[1]),
        text: point[2].replace(STRAY, '').trim(),
      });
    } else if (!(streaming && index === lines.length - 1)) {
      return { summary: null, body: markdown };
    }
  }
  return { summary: points, body: markdown.slice(match[0].length) };
}

/** Whether a block in `body` opens with the bold label, the way the detail
 * paragraphs a point jumps to do. */
export function opensWithLabel(body: string, label: string): boolean {
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(
    `^[ \\t]*(?:[-*][ \\t]+)?\\*\\*${escaped}:?\\*\\*`,
    'm',
  ).test(body);
}

/** The element id of the detail paragraph a point jumps to. */
export function pointAnchorId(prefix: string, label: string): string {
  const slug = label
    .toLocaleLowerCase('de')
    .normalize('NFKD')
    .replace(/\p{Mark}/gu, '')
    .replace(/[^\p{Letter}\p{Number}]+/gu, '-')
    .replace(/^-|-$/g, '');
  return `${prefix}-${slug}`;
}
