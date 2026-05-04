'use client';

import { useContextParties } from '@/components/providers/context-provider';
import VisuallyHidden from '@/components/visually-hidden';
import { MessageCitationsList } from '@/modules/guided-exploration/components/shared/message-citations-list';
import { PartyCard } from '@/modules/guided-exploration/components/shared/party-card';
import type {
  PartyPosition,
  SubtopicContent,
} from '@/modules/guided-exploration/types';
import { PartyPositionItem } from './party-position-item';

interface InitialContentMessageProps {
  content: SubtopicContent;
  messageId: string;
  /**
   * If true, render a placeholder card for each party from the active
   * context that has no entry in ``content.partyPositions``. Used in study
   * mode so participants see all assigned parties and aren't left to guess
   * why a party is missing.
   */
  showMissingPartiesPlaceholder?: boolean;
}

/**
 * Renders the initial subtopic content as a styled article/message
 */
export function InitialContentMessage({
  content,
  messageId,
  showMissingPartiesPlaceholder = false,
}: InitialContentMessageProps) {
  const contextParties = useContextParties();

  const positionByParty = new Map<string, PartyPosition>(
    content.partyPositions.map((p) => [p.party.toLowerCase(), p]),
  );

  const orderedEntries = (() => {
    if (!showMissingPartiesPlaceholder || !contextParties?.length) {
      return content.partyPositions.map((p) => ({
        partyId: p.party,
        position: p,
      }));
    }
    const seen = new Set<string>();
    const entries: { partyId: string; position: PartyPosition | null }[] = [];
    for (const party of contextParties) {
      const id = party.party_id.toLowerCase();
      seen.add(id);
      entries.push({
        partyId: party.party_id,
        position: positionByParty.get(id) ?? null,
      });
    }
    // Surface any positions for parties not in the current context (defensive)
    for (const position of content.partyPositions) {
      if (!seen.has(position.party.toLowerCase())) {
        entries.push({ partyId: position.party, position });
      }
    }
    return entries;
  })();

  return (
    <article className="space-y-4">
      {/* Party positions render as cards directly below the assistant
          summary text — no visible heading, so the whole leaf reads as a
          single chat reply. The heading stays for screen readers. */}
      {orderedEntries.length > 0 && (
        <>
          <VisuallyHidden>
            <h3>Parteipositionen</h3>
          </VisuallyHidden>
          <ul className="space-y-4">
            {orderedEntries.map(({ partyId, position }) =>
              position ? (
                <PartyPositionItem
                  key={partyId}
                  position={position}
                  citations={content.citations}
                />
              ) : (
                <li key={partyId} className="list-none">
                  <PartyCard partyId={partyId} className="opacity-70">
                    <p className="text-sm italic text-muted-foreground">
                      Diese Partei hat zu diesem Aspekt keine Position in ihrem
                      Wahlprogramm formuliert.
                    </p>
                  </PartyCard>
                </li>
              ),
            )}
          </ul>
        </>
      )}

      <MessageCitationsList
        citations={content.citations}
        messageId={messageId}
      />
    </article>
  );
}
