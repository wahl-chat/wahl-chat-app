/**
 * Fuzzy matching between a cited source snippet and a PDF page's text layer.
 *
 * PDF text extraction is noisy (line-break hyphenation, soft hyphens, arbitrary
 * whitespace between text items), so both sides are reduced to a bare
 * letters-and-digits stream before matching. The snippet is searched in fixed
 * windows rather than as one block, so a partial overlap (e.g. a chunk that
 * starts mid-page or carries a heading the page does not) still highlights the
 * parts that do appear. No match simply means no highlight.
 */

const WINDOW_CHARS = 60;
const MIN_WINDOW_CHARS = 24;

function isStreamChar(char: string): boolean {
  return /[\p{L}\p{N}]/u.test(char);
}

/** Letters+digits only, lowercased — the common denominator of PDF text noise. */
export function toStream(text: string): string {
  let stream = '';
  for (const char of text.toLowerCase()) {
    if (isStreamChar(char)) {
      stream += char;
    }
  }
  return stream;
}

/**
 * Text-item indices of a page's text layer that overlap the snippet.
 *
 * `items` are the page's text items in layer order (react-pdf's
 * `customTextRenderer` addresses them by index).
 */
export function matchSnippetItems(
  items: string[],
  snippet: string,
): Set<number> {
  const matched = new Set<number>();

  // Page stream + map from stream position back to the item that produced it.
  let pageStream = '';
  const itemAt: number[] = [];
  items.forEach((item, itemIndex) => {
    for (const char of item.toLowerCase()) {
      if (isStreamChar(char)) {
        pageStream += char;
        itemAt.push(itemIndex);
      }
    }
  });

  const snippetStream = toStream(snippet);
  if (snippetStream.length < MIN_WINDOW_CHARS || pageStream.length === 0) {
    return matched;
  }

  for (let start = 0; start < snippetStream.length; start += WINDOW_CHARS) {
    let window = snippetStream.slice(start, start + WINDOW_CHARS);
    if (window.length < MIN_WINDOW_CHARS) {
      // Short tail: re-anchor it to end at the snippet end so it stays distinctive.
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
    for (let i = pos; i < pos + window.length; i++) {
      matched.add(itemAt[i]);
    }
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
