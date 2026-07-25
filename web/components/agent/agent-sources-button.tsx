'use client';

import {
  type NumberedSource,
  SourcesDialog,
} from '@/components/chat/sources-dialog';
import { Button } from '@/components/ui/button';
import type { Source } from '@/lib/stores/chat-store.types';
import { BookMarkedIcon } from 'lucide-react';
import { useMemo } from 'react';

type Props = {
  sources: Source[];
  messageContent: string;
};

// Regex to match [party_id][N] or [party_id][N, M, ...] format
// e.g., [spd][0], [cdu][1], [spd][0, 1], [cdu][0,1,2]
const REFERENCE_PATTERN = /\[([a-z]+)]\[(\d+(?:,\s*\d+)*)]/g;

// Parse comma-separated indices from a match, e.g., "0, 1" -> [0, 1]
function parseIndices(indicesStr: string): number[] {
  return indicesStr.split(',').map((s) => Number.parseInt(s.trim(), 10));
}

// Group sources by party_id for lookup
function groupSourcesByParty(sources: Source[]): Map<string, Source[]> {
  const grouped = new Map<string, Source[]>();
  for (const source of sources) {
    if (!source.party_id) continue;
    const existing = grouped.get(source.party_id) || [];
    existing.push(source);
    grouped.set(source.party_id, existing);
  }
  return grouped;
}

function AgentSourcesButton({ sources, messageContent }: Props) {
  const [sourcesReferenced, sourcesNotReferenced] = useMemo(() => {
    const sourcesByParty = groupSourcesByParty(sources);
    const referencedKeys = new Set<string>(); // "party_id:index" format
    const orderedSources: NumberedSource[] = [];

    // Find all references in the message (in order of appearance). This running
    // counter MUST mirror agent-chat-markdown's buildReferenceMapping so the badge
    // number equals the in-text citation pill number.
    const matches = Array.from(messageContent.matchAll(REFERENCE_PATTERN));
    let displayNumber = 1;

    for (const match of matches) {
      const partyId = match[1];
      const indices = parseIndices(match[2]);

      for (const partyIndex of indices) {
        const key = `${partyId}:${partyIndex}`;

        // Only add if not already seen
        if (!referencedKeys.has(key)) {
          referencedKeys.add(key);

          const source = sourcesByParty.get(partyId)?.[partyIndex];
          if (source) {
            orderedSources.push({ source, displayNumber: displayNumber++ });
          }
        }
      }
    }

    // Find sources that weren't referenced
    const notReferenced: NumberedSource[] = [];
    for (const [partyId, partySources] of sourcesByParty.entries()) {
      for (let i = 0; i < partySources.length; i++) {
        if (!referencedKeys.has(`${partyId}:${i}`)) {
          notReferenced.push({
            source: partySources[i],
            displayNumber: displayNumber++,
          });
        }
      }
    }

    return [orderedSources, notReferenced];
  }, [messageContent, sources]);

  if (sourcesReferenced.length === 0 && sourcesNotReferenced.length === 0) {
    return null;
  }

  return (
    <SourcesDialog
      referenced={sourcesReferenced}
      notReferenced={sourcesNotReferenced}
      badgeClassName="bg-zinc-300 dark:bg-zinc-600"
      trigger={
        <Button variant="outline" className="h-8 px-2 text-xs">
          <BookMarkedIcon className="mr-1 size-4" />
          Quellen
        </Button>
      }
    />
  );
}

export default AgentSourcesButton;
