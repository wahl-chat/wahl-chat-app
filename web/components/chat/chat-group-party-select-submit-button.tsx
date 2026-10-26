import { Button } from '@/components/ui/button';
import { useRouter } from '@/i18n/navigation';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { useTranslations } from 'next-intl';
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
  const t = useTranslations('chat.partySelect');
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
        {addPartiesToChat ? t('submitChange') : t('submitStart')}
      </Button>
    </ResponsiveDialogClose>
  );
}

export default ChatGroupPartySelectSubmitButton;
