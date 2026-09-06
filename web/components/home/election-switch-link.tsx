'use client';

import ElectionSelectItems from '@/components/home/election-select-items';
import { Select, SelectContent, SelectTrigger } from '@/components/ui/select';
import type { Context } from '@/lib/firebase/firebase.types';
import { useRouter } from 'next/navigation';

type Props = {
  contexts: Context[];
  /** The election the page already leads with, pre-selected in the list. */
  selectedId?: string;
};

/**
 * The landing page's escape hatch from the featured election.
 *
 * Deliberately quiet: the hero already offers one election as its primary
 * action, and this only has to serve the visitor that election is wrong for.
 * Rendered outside a ContextProvider, so the list arrives as a prop.
 */
function ElectionSwitchLink({ contexts, selectedId }: Props) {
  const router = useRouter();

  if (contexts.length <= 1) return null;

  const handleContextChange = (contextId: string) => {
    if (contextId !== selectedId) {
      router.push(`/${contextId}`);
    }
  };

  return (
    <Select value={selectedId} onValueChange={handleContextChange}>
      <SelectTrigger
        className="h-auto w-auto gap-1 rounded-sm border-0 bg-transparent px-1 py-0.5 text-sm font-medium text-muted-foreground underline shadow-none hover:text-foreground [&>svg]:size-3 [&>svg]:opacity-100"
        aria-label="Eine andere Wahl auswählen"
      >
        Andere Wahl wählen
      </SelectTrigger>
      <SelectContent
        className="max-w-[calc(100vw-2rem)]"
        aria-label="Verfügbare Wahlen"
      >
        <ElectionSelectItems contexts={contexts} selectedId={selectedId} />
      </SelectContent>
    </Select>
  );
}

export default ElectionSwitchLink;
