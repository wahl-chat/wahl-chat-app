import { Button } from '@/components/ui/button';
import { useRouter } from 'next/navigation';
import { useEffect, useMemo } from 'react';
import { ResponsiveDialogClose } from './responsive-drawer-dialog';

type Props = {
  selectedPartyIds: string[];
  onSubmit: () => void;
  addPartiesToChat?: boolean;
};

function ChatGroupPartySelectSubmitButton({
  selectedPartyIds,
  onSubmit,
  addPartiesToChat,
}: Props) {
  const router = useRouter();

  const navigateUrl = useMemo(() => {
    const searchParams = new URLSearchParams();
    selectedPartyIds.forEach((partyId) => {
      searchParams.append('party_id', partyId);
    });

    return `/session?${searchParams.toString()}`;
  }, [selectedPartyIds]);

  const handleSubmit = () => {
    onSubmit();
    if (!addPartiesToChat) router.push(navigateUrl);
  };

  useEffect(() => {
    if (!addPartiesToChat) router.prefetch(navigateUrl);
  }, [navigateUrl]);

  return (
    <ResponsiveDialogClose asChild>
      <Button className="w-full" onClick={handleSubmit}>
        {addPartiesToChat ? 'Parteien ändern' : 'Vergleichschat starten'}
      </Button>
    </ResponsiveDialogClose>
  );
}

export default ChatGroupPartySelectSubmitButton;
