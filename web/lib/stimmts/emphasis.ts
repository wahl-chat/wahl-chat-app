/** A run of text, either plain or emphasised. */
export type EmphasisSegment = { text: string; strong: boolean };

const MARKER = '**';

export function hasBalancedEmphasis(text: string): boolean {
  return (text.split(MARKER).length - 1) % 2 === 0;
}

export function stripEmphasis(text: string): string {
  return text.split(MARKER).join('');
}

/**
 * Splits a key point at its `**` markers. Content is checked by the
 * validator, but a stray marker must never swallow the rest of the line, so
 * unbalanced text renders as written rather than half bold.
 */
export function splitEmphasis(text: string): EmphasisSegment[] {
  if (!hasBalancedEmphasis(text)) {
    return text === '' ? [] : [{ text, strong: false }];
  }
  // Between markers the parts alternate plain, strong, plain, …
  return text
    .split(MARKER)
    .map((part, index) => ({ text: part, strong: index % 2 === 1 }))
    .filter((segment) => segment.text !== '');
}
