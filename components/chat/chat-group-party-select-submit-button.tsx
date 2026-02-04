import { Button } from '@/components/ui/button';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo } from 'react';
import { ResponsiveDialogClose } from './responsive-drawer-dialog';

type Props = {
  selectedPartyIds: string[];
  onSubmit: () => void;
  addPartiesToChat?: boolean;
  contextId?: string;
};

function ChatGroupPartySelectSubmitButton({
  selectedPartyIds,
  onSubmit,
  addPartiesToChat,
  contextId = DEFAULT_CONTEXT_ID,
}: Props) {
  const router = useRouter();

  const navigateUrl = useMemo(() => {
    const searchParams = new URLSearchParams();
    selectedPartyIds.forEach((partyId) => {
      searchParams.append('party_id', partyId);
    });

    return `/${contextId}/session?${searchParams.toString()}`;
  }, [selectedPartyIds, contextId]);

  const handleSubmit = () => {
    onSubmit();
    if (!addPartiesToChat) router.push(navigateUrl);
  };

  useEffect(() => {
    if (!addPartiesToChat) router.prefetch(navigateUrl);
  }, [navigateUrl, addPartiesToChat, router]);

  return (
    <ResponsiveDialogClose asChild>
      <Button className="w-full" onClick={handleSubmit}>
        {addPartiesToChat ? 'Parteien ändern' : 'Vergleichschat starten'}
      </Button>
    </ResponsiveDialogClose>
  );
}

export default ChatGroupPartySelectSubmitButton;
