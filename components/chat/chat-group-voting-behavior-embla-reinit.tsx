import { useCarousel } from '@/components/ui/carousel';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { useEffect } from 'react';

type Props = {
  messageId: string;
  isExpanded: boolean;
};

function ChatGroupVotingBehaviorEmblaReinit({ messageId, isExpanded }: Props) {
  const embla = useCarousel();
  const isLoadingVotingBehavior = useChatStore(
    (state) => state.loading.votingBehaviorSummary === messageId,
  );
  const currentStreamedVotingBehavior = useChatStore(
    (state) => state.currentStreamedVotingBehavior,
  );

  useEffect(() => {
    reinitEmbla();
  }, [
    embla.api,
    isLoadingVotingBehavior,
    isExpanded,
    currentStreamedVotingBehavior,
  ]);

  const reinitEmbla = async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
    embla.api?.reInit();
  };

  return null;
}

export default ChatGroupVotingBehaviorEmblaReinit;
