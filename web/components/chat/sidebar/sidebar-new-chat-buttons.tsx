'use client';

import PartyCards from '@/components/party-cards';
import { useSidebar } from '@/components/ui/sidebar';

type Props = {
  contextId: string;
};

function SidebarNewChatButtons({ contextId }: Props) {
  const { setOpenMobile } = useSidebar();

  const handleNewChat = () => {
    setOpenMobile(false);
  };

  return (
    <PartyCards
      gridColumns={3}
      selectable={false}
      showWahlChatButton
      onPartyClicked={handleNewChat}
      contextId={contextId}
    />
  );
}

export default SidebarNewChatButtons;
