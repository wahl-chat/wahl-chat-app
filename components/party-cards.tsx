'use client';

import PartyCard from '@/components/party-card';
import { useElectionContext } from '@/components/providers/context-provider';
import { cn } from '@/lib/utils';
import { CircleXIcon, EllipsisIcon } from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import Logo from './chat/logo';
import { Button } from './ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from './ui/collapsible';

const INITIAL_PARTY_COUNT = 7;

type Props = {
  className?: string;
  selectedPartyIds?: string[];
  onPartyClicked?: (partyId: string) => void;
  selectable?: boolean;
  gridColumns?: number;
  showWahlChatButton?: boolean;
  contextId: string;
};

function PartyCards({
  className,
  selectedPartyIds,
  onPartyClicked,
  selectable = true,
  gridColumns = 4,
  showWahlChatButton = false,
  contextId,
}: Props) {
  const { parties } = useElectionContext();

  // Sort parties: parliament parties first, then non-parliament
  // Within each group, non-small parties come before small parties
  // Parties are already shuffled by ContextProvider
  const sortedParties = useMemo(() => {
    if (!parties) return [];

    const parliament = parties.filter((p) => p.is_already_in_parliament);
    const nonParliament = parties.filter((p) => !p.is_already_in_parliament);

    const sortBySmall = (a: (typeof parties)[0], b: (typeof parties)[0]) =>
      (a.is_small_party ? 1 : 0) - (b.is_small_party ? 1 : 0);

    return [
      ...parliament.sort(sortBySmall),
      ...nonParliament.sort(sortBySmall),
    ];
  }, [parties]);

  const initialParties = sortedParties.slice(0, INITIAL_PARTY_COUNT);
  const remainingParties = sortedParties.slice(INITIAL_PARTY_COUNT);

  const defaultShowMore = !!remainingParties.find((p) =>
    selectedPartyIds?.includes(p.party_id),
  );

  const [showMore, setShowMore] = useState(defaultShowMore);

  if (!parties) {
    // Loading is handled by the parent
    return null;
  }

  const sectionLabel = selectable
    ? 'Parteien zur Auswahl'
    : 'Verfügbare Parteien';

  return (
    <Collapsible open={showMore} onOpenChange={setShowMore} asChild>
      <section
        className={cn('grid w-full grid-cols-4 gap-2', className)}
        style={{
          gridTemplateColumns: `repeat(${gridColumns}, minmax(0, 1fr))`,
        }}
        aria-label={sectionLabel}
        role={selectable ? 'group' : 'navigation'}
      >
        {showWahlChatButton && (
          <Button
            className={cn(
              'flex aspect-square size-full items-center justify-center rounded-md',
              'border border-muted-foreground/20 bg-background dark:bg-zinc-900 hover:bg-muted p-0',
            )}
            type="button"
            tooltip="wahl.chat"
            asChild
          >
            <Link
              href={`/${contextId}/session`}
              onClick={() => onPartyClicked?.('wahl.chat')}
              aria-label="Chat mit wahl.chat starten"
            >
              <Logo className="!size-10" aria-hidden="true" />
            </Link>
          </Button>
        )}
        {initialParties.map((party) => (
          <PartyCard
            id={party.party_id}
            key={party.party_id}
            party={party}
            isSelected={selectedPartyIds?.includes(party.party_id)}
            onPartyClicked={onPartyClicked}
            selectable={selectable}
            contextId={contextId}
          />
        ))}
        {remainingParties.length > 0 && (
          <>
            <CollapsibleTrigger asChild>
              <Button
                variant="secondary"
                className={cn(
                  'flex aspect-square items-center justify-center',
                  'w-full h-fit border border-muted-foreground/20 overflow-hidden md:hover:bg-zinc-200 dark:md:hover:bg-zinc-700',
                  'text-center whitespace-normal text-muted-foreground flex flex-col items-center justify-center',
                  'text-xs md:text-sm gap-1 md:gap-2',
                )}
                aria-expanded={showMore}
                aria-label={
                  showMore
                    ? 'Weniger Parteien anzeigen'
                    : 'Mehr Parteien anzeigen'
                }
              >
                {showMore ? (
                  <CircleXIcon className="size-4" aria-hidden="true" />
                ) : (
                  <EllipsisIcon className="size-4" aria-hidden="true" />
                )}
                {gridColumns >= 4 &&
                  `${showMore ? 'Weniger' : 'Mehr'} Parteien`}
              </Button>
            </CollapsibleTrigger>

            <CollapsibleContent asChild>
              <div
                className="col-span-4 grid gap-2"
                style={{
                  gridColumn: `span ${gridColumns} / span ${gridColumns}`,
                  gridTemplateColumns: `repeat(${gridColumns}, minmax(0, 1fr))`,
                }}
                role="group"
                aria-label="Weitere Parteien"
              >
                {remainingParties.map((party) => (
                  <PartyCard
                    id={party.party_id}
                    key={party.party_id}
                    party={party}
                    isSelected={selectedPartyIds?.includes(party.party_id)}
                    onPartyClicked={onPartyClicked}
                    selectable={selectable}
                    contextId={contextId}
                  />
                ))}
              </div>
            </CollapsibleContent>
          </>
        )}
      </section>
    </Collapsible>
  );
}

export default PartyCards;
