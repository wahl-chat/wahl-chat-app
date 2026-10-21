'use client';

import ElectionSelectItems from '@/components/home/election-select-items';
import HeroCta from '@/components/landing/hero-cta';
import { Select, SelectContent, SelectTrigger } from '@/components/ui/select';
import type { Context } from '@/lib/firebase/firebase.types';
import { formatGermanDate } from '@/lib/utils';
import { CalendarIcon } from 'lucide-react';
import { useMemo, useState } from 'react';

/**
 * The hero's election cluster: which election the page is currently talking
 * about, when it is, and the call to action that takes you there.
 *
 * The name is a picker rather than a static label so a visitor can switch
 * without leaving the landing page. Icon, date, and CTA href all read from
 * the same selection so they cannot drift apart. A single election is not a
 * choice, so it stays a line of text.
 */

type Props = {
  featured: Context;
  contexts: Context[];
};

function HeroElection({ featured, contexts }: Props) {
  const [selectedId, setSelectedId] = useState(featured.context_id);

  const selected = useMemo(
    () =>
      contexts.find((context) => context.context_id === selectedId) ?? featured,
    [contexts, featured, selectedId],
  );

  const date = formatGermanDate(selected.date);
  const canSwitch = contexts.length > 1;

  return (
    <div className="flex w-full flex-col items-center gap-2 md:mb-auto">
      <div className="text-balance text-center font-medium text-foreground">
        <span>Deine Wahl: </span>
        {canSwitch ? (
          <Select value={selected.context_id} onValueChange={setSelectedId}>
            <SelectTrigger
              className="inline-flex h-auto w-auto max-w-full items-baseline justify-center gap-1 whitespace-normal border-0 bg-transparent p-0 text-base font-medium leading-normal text-foreground shadow-none ring-offset-0 hover:underline hover:decoration-muted-foreground/60 hover:underline-offset-4 focus:ring-0 focus-visible:ring-2 focus-visible:ring-ring [&>span]:line-clamp-none [&>svg]:size-3.5 [&>svg]:shrink-0 [&>svg]:opacity-50"
              aria-label={`Wahl auswählen. Aktuell ausgewählt: ${selected.name}`}
            >
              {selected.name}
            </SelectTrigger>
            <SelectContent
              align="center"
              collisionPadding={24}
              side="bottom"
              sideOffset={8}
              className="z-[60] max-h-[min(32rem,var(--radix-select-content-available-height))] max-w-[calc(100vw-2rem)] overflow-y-auto [&_[data-radix-select-viewport]]:h-auto [&_[data-radix-select-viewport]]:max-h-none [&_[data-radix-select-viewport]]:min-w-[min(100vw-2rem,20rem)]"
              aria-label="Verfügbare Wahlen"
            >
              <ElectionSelectItems
                contexts={contexts}
                selectedId={selected.context_id}
              />
            </SelectContent>
          </Select>
        ) : (
          selected.name
        )}
      </div>

      {date && (
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <CalendarIcon className="size-4 shrink-0" aria-hidden="true" />
          {date}
        </p>
      )}

      <div className="mt-2 flex w-full justify-center">
        <HeroCta context={selected} />
      </div>
    </div>
  );
}

export default HeroElection;
