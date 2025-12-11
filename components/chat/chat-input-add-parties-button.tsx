import { PlusIcon } from 'lucide-react';
import ChatGroupPartySelect from './chat-group-party-select';
import { useChatStore } from '@/components/providers/chat-store-provider';

type Props = {
  disabled: boolean;
};

function ChatInputAddPartiesButton({ disabled }: Props) {
  const partyIds = useChatStore((state) => state.partyIds);
  const setPartyIds = useChatStore((state) => state.setPartyIds);

  return (
    <div className="absolute left-2 top-2 z-40">
      <ChatGroupPartySelect
        selectedPartyIdsInStore={Array.from(partyIds)}
        onNewChat={(partyIds) => setPartyIds(partyIds)}
        addPartiesToChat
      >
        <button
          className="z-40 flex shrink-0 items-center gap-1 rounded-full bg-primary p-1 text-primary-foreground transition-all duration-200 ease-out enabled:hover:scale-95 disabled:cursor-not-allowed"
          disabled={disabled}
          type="button"
        >
          <PlusIcon className="size-4" />
        </button>
      </ChatGroupPartySelect>
    </div>
  );
}

export default ChatInputAddPartiesButton;
