/**
 * Citation Helpers
 * Shared hooks for citation rendering across the guided exploration UI.
 *
 * useCitationHandlers — for rendered messages with a citations array
 * useStreamingCitationMap — for streaming content where citations are parsed from text
 */

import { useCallback, useMemo } from 'react';

import { buildPdfUrl } from '@/lib/utils';
import type { Citation } from '@/modules/guided-exploration/types';

/**
 * Hook providing citation resolution for rendered messages.
 * Returns getReferenceName, getReferenceTooltip, and handleReferenceClick.
 *
 * @param citations - The citations array from the message
 */
export function useCitationHandlers(citations: Citation[]) {
  const getReferenceName = useCallback(
    (id: string): string | null => {
      const index = citations.findIndex((c) => c.id === id);
      return index >= 0 ? `${index + 1}` : null;
    },
    [citations],
  );

  const getReferenceTooltip = useCallback(
    (id: string): string | null => {
      const citation = citations.find((c) => c.id === id);
      if (!citation) return null;
      return `${citation.party} - Seite: ${citation.page}`;
    },
    [citations],
  );

  const handleReferenceClick = useCallback(
    (id: string) => {
      const citation = citations.find((c) => c.id === id);
      if (!citation?.url) return;

      const isPdfLink = citation.url.includes('.pdf');
      if (isPdfLink && citation.page) {
        const url = buildPdfUrl({
          url: citation.url,
          page: citation.page,
          source: citation.party,
          source_document: citation.document,
          document_publish_date: '',
        });
        window.open(url.toString(), '_blank');
      } else {
        window.open(citation.url, '_blank');
      }
    },
    [citations],
  );

  return { getReferenceName, getReferenceTooltip, handleReferenceClick };
}

/**
 * Hook providing citation ID → sequential number mapping for streaming content.
 * Parses [id] patterns from text and assigns 1, 2, 3... in order of appearance.
 *
 * @param content - The streaming markdown text
 */
export function useStreamingCitationMap(content: string) {
  const citationMap = useMemo(() => {
    const map = new Map<string, number>();
    const matches = content.matchAll(/\[([\w.-]+(?:\s*,\s*[\w.-]+)*)\]/g);
    for (const match of matches) {
      const ids = match[1].split(/\s*,\s*/);
      for (const id of ids) {
        if (!map.has(id) && id.includes('-') && !id.startsWith('PARTY')) {
          map.set(id, map.size + 1);
        }
      }
    }
    return map;
  }, [content]);

  const getReferenceName = useCallback(
    (id: string): string | null => {
      const num = citationMap.get(id);
      return num !== undefined ? `${num}` : null;
    },
    [citationMap],
  );

  return { getReferenceName };
}
