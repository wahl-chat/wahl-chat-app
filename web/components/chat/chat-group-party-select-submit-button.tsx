import { Button } from '@/components/ui/button';
import { buildChatSessionUrl } from '@/lib/chat-route';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo } from 'react';
import { ResponsiveDialogClose } from './responsive-drawer-dialog';

type Props = {
  selectedPartyIds: string[];
  onSubmit: () => void;
  addPartiesToChat?: boolean;
  selectionOnly?: boolean;
  contextId?: string;
};

function ChatGroupPartySelectSubmitButton({
  selectedPartyIds,
  onSubmit,
  addPartiesToChat,
  selectionOnly = false,
  contextId = DEFAULT_CONTEXT_ID,
}: Props) {
  const router = useRouter();

  const navigateUrl = useMemo(() => {
    return buildChatSessionUrl({ contextId, partyIds: selectedPartyIds });
  }, [selectedPartyIds, contextId]);

  const handleSubmit = () => {
    onSubmit();
    if (!addPartiesToChat && !selectionOnly) router.push(navigateUrl);
  };

  useEffect(() => {
    if (!addPartiesToChat && !selectionOnly) router.prefetch(navigateUrl);
  }, [navigateUrl, addPartiesToChat, selectionOnly, router]);

  return (
    <ResponsiveDialogClose asChild>
      <Button className="w-full" onClick={handleSubmit}>
        {selectionOnly
          ? 'Auswahl übernehmen'
          : addPartiesToChat
            ? 'Parteien ändern'
            : 'Vergleichschat starten'}
      </Button>
    </ResponsiveDialogClose>
  );
}

export default ChatGroupPartySelectSubmitButton;
