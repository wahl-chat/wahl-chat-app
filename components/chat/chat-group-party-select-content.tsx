'use client';

import PartyCards from '@/components/party-cards';
import { useCurrentContext } from '@/components/providers/context-provider';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { track } from '@vercel/analytics/react';
import { useState } from 'react';
import { toast } from 'sonner';
import ChatGroupPartySelectSubmitButton from './chat-group-party-select-submit-button';
import { ResponsiveDialogFooter } from './responsive-drawer-dialog';

type Props = {
  selectedPartyIdsInStore?: string[];
  onNewChat?: (partyIds: string[]) => void;
  addPartiesToChat?: boolean;
  contextId?: string;
};

export const MAX_SELECTABLE_PARTIES = 7;

function ChatGroupPartySelectContent({
  selectedPartyIdsInStore,
  onNewChat,
  addPartiesToChat,
  contextId: propContextId,
}: Props) {
  // Try to get context from provider, fall back to prop or default
  let contextId = propContextId ?? DEFAULT_CONTEXT_ID;
  try {
    const currentContext = useCurrentContext();
    contextId = currentContext?.context_id ?? contextId;
  } catch {
    // Context provider not available, use prop or default
  }

  const [selectedPartyIds, setSelectedPartyIds] = useState<string[]>(
    selectedPartyIdsInStore ?? [],
  );

  const handlePartyClicked = (partyId: string) => {
    if (selectedPartyIds.includes(partyId)) {
      setSelectedPartyIds((prev) => prev.filter((id) => id !== partyId));
      return;
    }

    if (selectedPartyIds.length >= MAX_SELECTABLE_PARTIES) {
      toast.error(
        `Du kannst nur maximal ${MAX_SELECTABLE_PARTIES} Parteien auswählen`,
      );
      return;
    }

    setSelectedPartyIds((prev) => {
      return [...prev, partyId];
    });
  };

  const handleNewChat = () => {
    track('chat_group_party_select_submit', {
      party_ids: selectedPartyIds.join(','),
      context: contextId,
    });
    onNewChat?.(selectedPartyIds);
  };

  return (
    <>
      <PartyCards
        className="px-4 pb-2 md:px-0 md:pb-0"
        onPartyClicked={handlePartyClicked}
        selectedPartyIds={selectedPartyIds}
        contextId={contextId}
      />
      <ResponsiveDialogFooter className="pt-2">
        <ChatGroupPartySelectSubmitButton
          selectedPartyIds={selectedPartyIds}
          onSubmit={handleNewChat}
          addPartiesToChat={addPartiesToChat}
          contextId={contextId}
        />
      </ResponsiveDialogFooter>
    </>
  );
}

export default ChatGroupPartySelectContent;
