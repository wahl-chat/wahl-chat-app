'use client';

import { buildPdfUrl } from '@/lib/utils';
import type { Citation } from '@/modules/guided-exploration/types';
import { useId, useMemo } from 'react';

interface MessageCitationsListProps {
  citations: Citation[];
  /**
   * Owning message id. Combined with the citation id to form a stable
   * React key — the same source can legitimately appear across multiple
   * messages, so a bare `citation.id` collides at the React tree level.
   */
  messageId: string;
}

function buildCitationHref(citation: Citation): string | undefined {
  if (!citation.url) return undefined;
  const isPdfLink = citation.url.includes('.pdf');
  if (isPdfLink && citation.page) {
    return buildPdfUrl({
      url: citation.url,
      page: citation.page,
      source: citation.party,
      source_document: citation.document,
      document_publish_date: '',
    }).toString();
  }
  return citation.url;
}

function formatCitation(citation: Citation): string {
  const parts = [citation.party, citation.document];
  if (citation.section) parts.push(citation.section);
  if (citation.page) parts.push(`Seite ${citation.page}`);
  return parts.join(', ');
}

/**
 * Screen-reader-only footnote list rendered at the end of an assistant
 * message. Mirrors the inline `[1]`, `[2]`... citation markers so SR users
 * can review all cited sources without the inline markers interrupting the
 * reading flow. Sighted users still see the inline markers with tooltips.
 */
export function MessageCitationsList({
  citations,
  messageId,
}: MessageCitationsListProps) {
  const headingId = useId();
  // Defensive dedupe at the render boundary: backend occasionally lists
  // the same source twice (one per party position quoting it), and not all
  // ingest paths in `useSSE` currently dedupe. Doing it here means future
  // event handlers don't need to remember.
  const uniqueCitations = useMemo(() => {
    const seen = new Set<string>();
    return citations.filter((c) => {
      if (seen.has(c.id)) return false;
      seen.add(c.id);
      return true;
    });
  }, [citations]);

  if (uniqueCitations.length === 0) return null;

  return (
    <section aria-labelledby={headingId} className="sr-only">
      <h4 id={headingId}>Quellen zu dieser Antwort</h4>
      <ol>
        {uniqueCitations.map((citation, index) => {
          const href = buildCitationHref(citation);
          const label = `Quelle ${index + 1}: ${formatCitation(citation)}`;
          // `sr-` prefix keeps these keys in their own namespace so they
          // can never collide with inline citation keys elsewhere in the
          // tree (those use `citation.id` directly inside scoped subtrees).
          return (
            <li key={`sr-${messageId}-${citation.id}`} value={index + 1}>
              {href ? (
                // tabIndex={-1}: this list lives inside a `sr-only` block.
                // Without it, sighted keyboard users tab into the (1×1
                // absolutely-positioned) link and the browser scrolls the
                // chat container to the top to reveal it — leaving the
                // visible area looking blank. Screen readers reach it via
                // virtual cursor / link list, which is unaffected.
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  tabIndex={-1}
                >
                  {label}
                </a>
              ) : (
                label
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
