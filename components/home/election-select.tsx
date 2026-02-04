'use client';

import { ContextIcon } from '@/components/context-icon';
import {
  useContexts,
  useCurrentContext,
} from '@/components/providers/context-provider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from '@/components/ui/select';
import type { Context } from '@/lib/firebase/firebase.types';
import { formatGermanDate } from '@/lib/utils';
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

export function ElectionSelect() {
  const currentContext = useCurrentContext();
  const contexts = useContexts();
  const router = useRouter();

  const handleContextChange = (contextId: string) => {
    if (contextId !== currentContext.context_id) {
      router.push(`/${contextId}`);
    }
  };

  // Don't show selector if there's only one context
  if (contexts.length <= 1) {
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
      <SelectTrigger
        className="h-auto w-full border-border bg-muted/50 px-3 py-2 [&>svg]:size-4 [&>svg]:text-muted-foreground"
        aria-label={`Wahl auswählen. Aktuell ausgewählt: ${currentContext.name}`}
      >
        <CompactElectionContent context={currentContext} />
      </SelectTrigger>
      <SelectContent
        className="max-w-[calc(100vw-2rem)]"
        aria-label="Verfügbare Wahlen"
      >
        {contexts.map((ctx) => {
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
      </SelectContent>
    </Select>
  );
}

export default ElectionSelect;
