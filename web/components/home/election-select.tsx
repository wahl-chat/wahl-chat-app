'use client';

import { ContextIcon } from '@/components/context-icon';
import ElectionSelectItems from '@/components/home/election-select-items';
import {
  useContexts,
  useCurrentContext,
} from '@/components/providers/context-provider';
import { Select, SelectContent, SelectTrigger } from '@/components/ui/select';
import type { Context } from '@/lib/firebase/firebase.types';
import { formatGermanDate } from '@/lib/utils';
import { CalendarIcon, MapPinIcon } from 'lucide-react';
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

export function ElectionSelect() {
  const currentContext = useCurrentContext();
  const contexts = useContexts();
  const router = useRouter();

  const handleContextChange = (contextId: string) => {
    if (contextId !== currentContext.context_id) {
      router.push(`/${contextId}`);
    }
  };

  // A lone context is not a choice — render it as a status line instead.
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
        <ElectionSelectItems
          contexts={contexts}
          selectedId={currentContext.context_id}
        />
      </SelectContent>
    </Select>
  );
}

export default ElectionSelect;
