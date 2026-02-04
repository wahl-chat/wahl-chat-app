'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { useContextParties } from '@/components/providers/context-provider';
import Link from 'next/link';
import Logo from './logo';
import PartyDetailPopover from './party-detail-popover';

type Props = {
  showPartyPopover?: boolean;
};

function ChatHeaderTitleDescription({ showPartyPopover = true }: Props) {
  const partyIds = useChatStore((state) => state.partyIds);
  const parties = useContextParties([...partyIds]);

  return (
    <div className="flex min-w-0 items-center gap-2">
      <div className="flex shrink-0 flex-col">
        <Link href="/">
          <Logo variant="large" className="w-24" />
        </Link>
      </div>
      {showPartyPopover && parties && parties?.length > 0 && (
        <div className="shrink-0">
          <PartyDetailPopover parties={parties} />
        </div>
      )}
    </div>
  );
}

export default ChatHeaderTitleDescription;
