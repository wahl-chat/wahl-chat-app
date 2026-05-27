'use client';

import { useContextParties } from '@/components/providers/context-provider';
import { MessageCitationsList } from '@/modules/guided-exploration/components/shared/message-citations-list';
import { MessageNavLinks } from '@/modules/guided-exploration/components/shared/message-nav-links';
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
  /**
   * Heading id of the next message in the transcript. Drives the "jump to
   * next message" skip-link rendered before this turn's sources.
   */
  nextHeadingId?: string | null;
  /** Contextual link text for the next-message skip-link. */
  nextLabel?: string;
  /**
   * Target id for the "jump to input" skip-link. Usually the leaf composer
   * (`leaf-chat-input`), but switches to the closure prompt's heading when the
   * LLM has replaced the composer with a closure prompt.
   */
  inputId?: string;
  /** Contextual link text for the "jump to input" skip-link. */
  inputLabel?: string;
  /**
   * Content rendered at the end of this turn — after the answer, before the
   * skip-links and sources. Used to attach the leaf closure prompt to the
   * latest turn so it reads ahead of the "jump to input" skip-link.
   */
  trailing?: React.ReactNode;
}

/**
 * Renders the party-position cards of the opening leaf turn. No wrapper
 * landmark or section heading — the cards flow directly beneath the
 * "Initiale Übersicht" heading owned by the leaf summary, so the whole opening
 * turn reads as a single chat message.
 */
export function InitialContentMessage({
  content,
  messageId,
  showMissingPartiesPlaceholder = false,
  nextHeadingId = null,
  nextLabel,
  inputId = 'leaf-chat-input',
  inputLabel = 'Zum Eingabefeld springen, um eine eigene Frage zu stellen',
  trailing,
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
    <div className="space-y-4">
      {/* Party positions render as cards directly below the assistant summary
          text — flowing, no list/landmark wrapper, so the whole opening turn
          reads as a single chat reply under the "Initiale Übersicht" heading. */}
      {orderedEntries.length > 0 &&
        orderedEntries.map(({ partyId, position }) =>
          position ? (
            <PartyPositionItem
              key={partyId}
              position={position}
              citations={content.citations}
            />
          ) : (
            <PartyCard key={partyId} partyId={partyId} className="opacity-70">
              <p className="text-sm italic text-muted-foreground">
                Diese Partei hat zu diesem Aspekt keine Position in ihrem
                Wahlprogramm formuliert.
              </p>
            </PartyCard>
          ),
        )}

      {orderedEntries.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Stell gerne weitere Rückfragen. Ich sage dir Bescheid, wenn wir die
          Informationen, die die Parteien zu diesem Thema bieten, abgehandelt
          haben.
        </p>
      )}

      {trailing}

      {/* Before the sources: skip straight to the next message or the
          composer, so SR users aren't forced to arrow through every citation. */}
      <MessageNavLinks
        nextHeadingId={nextHeadingId}
        nextLabel={nextLabel}
        inputId={inputId}
        inputLabel={inputLabel}
      />
      <MessageCitationsList
        citations={content.citations}
        messageId={messageId}
      />
    </div>
  );
}
