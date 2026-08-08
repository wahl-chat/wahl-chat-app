'use client';

import { ContextIcon } from '@/components/context-icon';
import { useElectionContext } from '@/components/providers/context-provider';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
} from '@/components/ui/select';
import { splitElectionsByDate } from '@/lib/elections';
import type { Context } from '@/lib/firebase/firebase.types';
import { cn, formatGermanDate } from '@/lib/utils';
import { CalendarIcon, CheckIcon, MapPinIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';

function CompactElectionContent({ context }: { context: Context }) {
  const formattedDate = formatGermanDate(context.date, 'short');

  return (
    <div className="flex min-w-0 flex-1 items-center gap-2">
      <ContextIcon context={context} />
      <span className="truncate text-sm font-medium text-foreground">
        {context.name}
      </span>
      <span className="hidden shrink-0 items-center gap-3 text-xs text-muted-foreground sm:flex">
        {formattedDate && (
          <span className="flex items-center gap-1">
            <CalendarIcon className="size-3" />
            <span>{formattedDate}</span>
          </span>
        )}
        {context.location_name && (
          <span className="flex items-center gap-1">
            <MapPinIcon className="size-3" />
            <span>{context.location_name}</span>
          </span>
        )}
      </span>
    </div>
  );
}

function DropdownElectionContent({
  context,
  isSelected,
}: {
  context: Context;
  isSelected?: boolean;
}) {
  const formattedDate = formatGermanDate(context.date, 'long');

  return (
    <div className="flex w-full items-start gap-3 py-1">
      <ContextIcon context={context} className="mt-0.5 size-8 shrink-0" />
      <div className="flex min-w-0 flex-1 flex-col items-start gap-1">
        <span className="text-sm font-medium leading-tight text-foreground">
          {context.name}
        </span>
        <div className="flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground">
          {formattedDate && (
            <span className="flex items-center gap-1">
              <CalendarIcon className="size-3 shrink-0" />
              <span className="leading-none">{formattedDate}</span>
            </span>
          )}
          {context.location_name && (
            <span className="flex items-center gap-1">
              <MapPinIcon className="size-3 shrink-0" />
              <span className="leading-none">{context.location_name}</span>
            </span>
          )}
        </div>
      </div>
      {isSelected && (
        <CheckIcon className="mt-0.5 size-4 shrink-0 text-primary" />
      )}
    </div>
  );
}

type Props = {
  /** Falls back to the ContextProvider. Pass explicitly outside one, e.g. on /. */
  contexts?: Context[];
  currentContext?: Context;
  /** Label above the trigger. Omitted on context pages, where the page itself says which election it is. */
  label?: string;
  /** Draws attention to the trigger when choosing an election is the page's main action. */
  highlight?: boolean;
};

export function ElectionSelect({
  contexts: contextsProp,
  currentContext: currentContextProp,
  label,
  highlight,
}: Props = {}) {
  const electionContext = useElectionContext({ optional: true });
  const router = useRouter();

  const contexts = contextsProp ?? electionContext?.contexts ?? [];
  const currentContext = currentContextProp ?? electionContext?.context;

  const handleContextChange = (contextId: string) => {
    if (contextId !== currentContext?.context_id) {
      router.push(`/${contextId}`);
    }
  };

  const { upcoming: upcomingElections, past: pastElections } =
    splitElectionsByDate(contexts);

  if (!currentContext) return null;

  // A lone context is not a choice — render it as a status line instead. Only
  // applies inside a provider: where the selector is the page's main action the
  // dropdown has to stay operable.
  if (contexts.length <= 1 && electionContext) {
    return (
      <div
        className="flex w-full items-center gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2"
        role="status"
        aria-label={`Aktuelle Wahl: ${currentContext.name}`}
      >
        <CompactElectionContent context={currentContext} />
      </div>
    );
  }

  return (
    <Select
      value={currentContext.context_id}
      onValueChange={handleContextChange}
    >
      {label && (
        <span className="mb-1 block text-sm font-semibold text-foreground">
          {label}
        </span>
      )}
      <SelectTrigger
        className={cn(
          'h-auto w-full border-border bg-muted/50 px-3 py-2 [&>svg]:size-4 [&>svg]:text-muted-foreground',
          highlight &&
            'border-primary/40 animate-election-select-pulse motion-reduce:animate-none',
        )}
        aria-label={`Wahl auswählen. Aktuell ausgewählt: ${currentContext.name}`}
      >
        <CompactElectionContent context={currentContext} />
      </SelectTrigger>
      <SelectContent
        className="max-w-[calc(100vw-2rem)]"
        aria-label="Verfügbare Wahlen"
      >
        {upcomingElections.map((ctx) => {
          const isSelected = ctx.context_id === currentContext.context_id;
          const formattedDate = formatGermanDate(ctx.date, 'long');
          const ariaLabel = `${ctx.name}${formattedDate ? `, ${formattedDate}` : ''}${ctx.location_name ? `, ${ctx.location_name}` : ''}${isSelected ? ' (ausgewählt)' : ''}`;

          return (
            <SelectItem
              key={ctx.context_id}
              value={ctx.context_id}
              className="block w-full cursor-pointer px-3 py-2 [&>span:first-child]:hidden [&>span]:whitespace-normal"
              aria-label={ariaLabel}
            >
              <DropdownElectionContent context={ctx} isSelected={isSelected} />
            </SelectItem>
          );
        })}

        {pastElections.length > 0 && (
          <>
            <SelectSeparator className="bg-border/50" />
            <SelectGroup>
              <SelectLabel className="pl-3 text-xs font-normal text-muted-foreground/70">
                Vergangene Wahlen
              </SelectLabel>
              {pastElections.map((ctx) => {
                const isSelected = ctx.context_id === currentContext.context_id;
                const formattedDate = formatGermanDate(ctx.date, 'long');
                const ariaLabel = `${ctx.name}${formattedDate ? `, ${formattedDate}` : ''}${ctx.location_name ? `, ${ctx.location_name}` : ''}${isSelected ? ' (ausgewählt)' : ''}`;

                return (
                  <SelectItem
                    key={ctx.context_id}
                    value={ctx.context_id}
                    className="block w-full cursor-pointer px-3 py-2 [&>span:first-child]:hidden [&>span]:whitespace-normal"
                    aria-label={ariaLabel}
                  >
                    <DropdownElectionContent
                      context={ctx}
                      isSelected={isSelected}
                    />
                  </SelectItem>
                );
              })}
            </SelectGroup>
          </>
        )}
      </SelectContent>
    </Select>
  );
}

export default ElectionSelect;
