'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { isProlificStudy } from '@/lib/prolific-study/prolific-metadata';
import { getProlificWahlChatSessionConfig } from '@/lib/prolific-study/prolific-server';
import { useEffect, useState } from 'react';
import ChatProlificCompletion from './chat-prolific-completion';
import ChatProlificDisclaimer from './chat-prolific-disclaimer';
import ChatProlificProgress from './chat-prolific-progress';

function ChatProlificWrapper() {
  const [isProlific, setIsProlific] = useState<boolean | null>(null);
  const prolificMinInteractions = useChatStore(
    (state) => state.prolificMinInteractions,
  );
  const setProlificConfig = useChatStore((state) => state.setProlificConfig);

  // Check after mount to avoid hydration mismatch
  useEffect(() => {
    setIsProlific(isProlificStudy());
  }, []);

  // Fetch config when we know it's a prolific session
  useEffect(() => {
    if (isProlific && prolificMinInteractions === undefined) {
      getProlificWahlChatSessionConfig().then(setProlificConfig);
    }
  }, [isProlific, prolificMinInteractions, setProlificConfig]);

  // Don't render until we know if it's a prolific session
  if (isProlific === null) {
    return null;
  }

  // Not a prolific session
  if (!isProlific) {
    return null;
  }

  // Waiting for config to load
  if (prolificMinInteractions === undefined) {
    return null;
  }

  return (
    <>
      <ChatProlificDisclaimer minInteractions={prolificMinInteractions} />
      <ChatProlificCompletion minInteractions={prolificMinInteractions} />
      <ChatProlificProgress minInteractions={prolificMinInteractions} />
    </>
  );
}

export default ChatProlificWrapper;
