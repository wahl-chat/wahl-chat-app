'use client';

import ChatGroupPartySelect from '@/components/chat/chat-group-party-select';
import ElectionSelect from '@/components/home/election-select';
import HomePartyCards from '@/components/home/home-party-cards';
import LoadingPartyCards from '@/components/home/loading-party-cards';
import { useElectionContext } from '@/components/providers/context-provider';
import { Button } from '@/components/ui/button';
import { GitCompareIcon, MousePointerClickIcon } from 'lucide-react';

type Props = {
  contextId: string;
};

export function ElectionPartySelector({ contextId }: Props) {
  const { context, partyCount, parties } = useElectionContext();

  // Parties come from the server layout, so there is nothing to wait for; the
  // skeleton only covers the case where they are genuinely absent.
  const isLoading = !parties;

  return (
    <div
      className="flex w-full flex-col gap-6"
      role="group"
      aria-label="Wahl und Parteiauswahl"
    >
      {/* Election Context Banner */}
      <section aria-labelledby="election-context">
        <span id="election-context" className="sr-only">
          Aktuelle Wahl
        </span>
        <ElectionSelect />
      </section>

      {/* Party Selection - Main Focus */}
      <section
        className="flex flex-col gap-3"
        aria-labelledby="party-selection"
      >
        {/* The page's only h1. Kept at the visual size of the old h2 — the tag
            and the text are what carry the signal, not the type scale. */}
        <h1
          id="party-selection"
          className="flex items-center justify-center gap-2 text-center text-base font-semibold text-foreground"
        >
          <MousePointerClickIcon
            className="size-7 shrink-0"
            aria-hidden="true"
          />
          {context.name} – wähle eine Partei für den Chat
        </h1>

        {isLoading ? (
          <LoadingPartyCards
            partyCount={Math.min(partyCount || 0, 8)}
            className="mt-1"
            gridColumns={4}
          />
        ) : (
          <HomePartyCards contextId={contextId} />
        )}

        <ChatGroupPartySelect contextId={contextId}>
          <Button
            className="w-full max-w-xl whitespace-normal border border-border"
            variant="secondary"
            disabled={isLoading}
            aria-label="Mehrere Parteien zum Vergleichen auswählen"
          >
            <GitCompareIcon aria-hidden="true" />
            Wähle mehrere Parteien zum Vergleichen
          </Button>
        </ChatGroupPartySelect>
      </section>
    </div>
  );
}

export default ElectionPartySelector;
