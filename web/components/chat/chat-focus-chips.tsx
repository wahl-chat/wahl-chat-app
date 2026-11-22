'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { useContextParties } from '@/components/providers/context-provider';
import { XIcon } from 'lucide-react';

type Props = {
  disabled: boolean;
};

/** The general chat's party focus, removable one by one. */
function ChatFocusChips({ disabled }: Props) {
  const partyIds = useChatStore((state) => state.partyIds);
  const setPartyIds = useChatStore((state) => state.setPartyIds);
  const parties = useContextParties();

  if (partyIds.size === 0) {
    return null;
  }
  const ids = [...partyIds];

  return (
    <div className="mb-2 flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-muted-foreground">Fokus:</span>
      {ids.map((id) => {
        const name = parties?.find((p) => p.party_id === id)?.name ?? id;
        return (
          <span
            key={id}
            className="flex items-center gap-1 rounded-full border border-input bg-muted py-0.5 pl-2.5 pr-1 text-xs"
          >
            {name}
            <button
              type="button"
              disabled={disabled}
              onClick={() => setPartyIds(ids.filter((other) => other !== id))}
              className="-my-1 flex size-6 items-center justify-center rounded-full transition-colors enabled:hover:bg-background disabled:cursor-not-allowed"
              aria-label={`${name} aus dem Fokus entfernen`}
            >
              <XIcon className="size-3.5" />
            </button>
          </span>
        );
      })}
    </div>
  );
}

export default ChatFocusChips;
