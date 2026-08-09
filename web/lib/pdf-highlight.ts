/**
 * Fuzzy matching between a cited source snippet and a PDF page's text layer.
 *
 * PDF text extraction is noisy, so both sides are reduced to a bare
 * letters-only stream before matching:
 * - hyphenation and arbitrary whitespace between text items disappear;
 * - digits are dropped deliberately — protocol and manifesto PDFs interleave
 *   LINE NUMBERS with the text ("Russ-43 land"), which would break every
 *   window that crosses a line, and chunk text never carries them.
 *
 * The snippet is searched in fixed windows rather than as one block, so a
 * partial overlap (a chunk that starts mid-page, or carries a running
 * header/footer from extraction) still anchors the parts that appear. Matched
 * ranges then cluster by stream adjacency AND vertical position — a footer is
 * often stream-adjacent to the body (drawn right before it) but hundreds of
 * points away vertically — and only the largest cluster is highlighted.
 * No match simply means no highlight.
 */

const WINDOW_CHARS = 60;
const MIN_WINDOW_CHARS = 24;
// Matched ranges merge when both this close in the stream…
const MERGE_GAP_CHARS = 120;
// …and this close vertically (PDF text-space units; a page is ~842 tall,
// body lines sit ~15-25 apart, a footer is several hundred away).
const MERGE_Y_UNITS = 150;

export type HighlightTextItem = {
  str: string;
  /** Vertical position in PDF text space (transform[5]); null when unknown. */
  y: number | null;
};

function isStreamChar(char: string): boolean {
  return /\p{L}/u.test(char);
}

/** Letters only, lowercased — the common denominator of PDF text noise. */
export function toStream(text: string): string {
  let stream = '';
  for (const char of text.toLowerCase()) {
    if (isStreamChar(char)) {
      stream += char;
    }
  }
  return stream;
}

type Range = { start: number; end: number; y: number | null };

/**
 * Text-item indices of a page's text layer that overlap the snippet.
 *
 * `items` are the page's text items in layer order (react-pdf's
 * `customTextRenderer` addresses them by index).
 */
export function matchSnippetItems(
  items: HighlightTextItem[],
  snippet: string,
): Set<number> {
  const matched = new Set<number>();

  // Page stream + per-char maps back to the item and its y position.
  let pageStream = '';
  const itemAt: number[] = [];
  const yAt: Array<number | null> = [];
  items.forEach((item, itemIndex) => {
    for (const char of item.str.toLowerCase()) {
      if (isStreamChar(char)) {
        pageStream += char;
        itemAt.push(itemIndex);
        yAt.push(item.y);
      }
    }
  });

  const snippetStream = toStream(snippet);
  if (snippetStream.length < MIN_WINDOW_CHARS || pageStream.length === 0) {
    return matched;
  }

  const ranges: Range[] = [];
  for (let start = 0; start < snippetStream.length; start += WINDOW_CHARS) {
    let window = snippetStream.slice(start, start + WINDOW_CHARS);
    if (window.length < MIN_WINDOW_CHARS) {
      // Short tail: only usable when the whole snippet fits one window.
      if (snippetStream.length < WINDOW_CHARS) {
        window = snippetStream;
      } else {
        break;
      }
    }
    const pos = pageStream.indexOf(window);
    if (pos === -1) {
      continue;
    }
    ranges.push({ start: pos, end: pos + window.length, y: yAt[pos] });
  }
  if (ranges.length === 0) {
    return matched;
  }

  // Merge ranges that are close in the stream AND on the page; keep the
  // largest merged cluster (by matched span).
  ranges.sort((a, b) => a.start - b.start);
  const clusters: Range[] = [];
  for (const range of ranges) {
    const last = clusters[clusters.length - 1];
    const nearInStream = last && range.start - last.end <= MERGE_GAP_CHARS;
    const nearOnPage =
      last &&
      (last.y === null ||
        range.y === null ||
        Math.abs(last.y - range.y) <= MERGE_Y_UNITS);
    if (last && nearInStream && nearOnPage) {
      last.end = Math.max(last.end, range.end);
      last.y = range.y ?? last.y;
    } else {
      clusters.push({ ...range });
    }
  }
  const largest = clusters.reduce((best, cluster) =>
    cluster.end - cluster.start > best.end - best.start ? cluster : best,
  );
  for (let i = largest.start; i < largest.end; i++) {
    matched.add(itemAt[i]);
  }

  return matched;
}

export function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}
