'use client';

import { ContextIcon } from '@/components/context-icon';
import {
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
} from '@/components/ui/select';
import { splitElectionsByDate } from '@/lib/elections';
import type { Context } from '@/lib/firebase/firebase.types';
import { formatGermanDate } from '@/lib/utils';
import { CalendarIcon, CheckIcon, MapPinIcon } from 'lucide-react';

function ElectionRow({
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

function ElectionOption({
  context,
  isSelected,
}: {
  context: Context;
  isSelected: boolean;
}) {
  const formattedDate = formatGermanDate(context.date, 'long');
  const label = `${context.name}${formattedDate ? `, ${formattedDate}` : ''}${
    context.location_name ? `, ${context.location_name}` : ''
  }${isSelected ? ' (ausgewählt)' : ''}`;

  return (
    <SelectItem
      value={context.context_id}
      // Hiding the first span drops the built-in check indicator; ElectionRow
      // draws its own, aligned with the two-line content.
      className="block w-full cursor-pointer px-3 py-2 [&>span:first-child]:hidden [&>span]:whitespace-normal"
      aria-label={label}
    >
      <ElectionRow context={context} isSelected={isSelected} />
    </SelectItem>
  );
}

type Props = {
  contexts: Context[];
  selectedId?: string;
};

/**
 * The options for every election picker on the site: upcoming ones first,
 * concluded ones behind a separator so they read as an archive rather than a
 * choice of equal standing.
 */
function ElectionSelectItems({ contexts, selectedId }: Props) {
  const { upcoming, past } = splitElectionsByDate(contexts);

  return (
    <>
      {upcoming.map((context) => (
        <ElectionOption
          key={context.context_id}
          context={context}
          isSelected={context.context_id === selectedId}
        />
      ))}

      {past.length > 0 && (
        <>
          <SelectSeparator className="bg-border/50" />
          <SelectGroup>
            <SelectLabel className="pl-3 text-xs font-normal text-muted-foreground/70">
              Vergangene Wahlen
            </SelectLabel>
            {past.map((context) => (
              <ElectionOption
                key={context.context_id}
                context={context}
                isSelected={context.context_id === selectedId}
              />
            ))}
          </SelectGroup>
        </>
      )}
    </>
  );
}

export default ElectionSelectItems;
