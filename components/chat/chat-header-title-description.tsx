'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { useParties } from '@/components/providers/parties-provider';
import Link from 'next/link';
import Logo from './logo';
import PartyDetailPopover from './party-detail-popover';

type Props = {
  showPartyPopover?: boolean;
};

function ChatHeaderTitleDescription({ showPartyPopover = true }: Props) {
  const partyIds = useChatStore((state) => state.partyIds);
  const parties = useParties([...partyIds]);

  return (
    <div className="flex min-w-0 grow items-center gap-2">
      <div className="flex min-w-0 flex-col">
        <Link href="/">
          <Logo variant="large" className="w-24" />
        </Link>
      </div>
      {showPartyPopover && parties && parties?.length > 0 && (
        <PartyDetailPopover parties={parties} />
      )}
    </div>
  );
}

export default ChatHeaderTitleDescription;
