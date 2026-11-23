import ChatProlificWrapper from '@/components/chat/chat-prolific-wrapper';
import ChatStudyWrapper from '@/components/chat/chat-study-wrapper';
import AiDisclaimer from '@/components/legal/ai-disclaimer';
import LoadingSpinner from '@/components/loading-spinner';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import {
  getCurrentUser,
  getSystemStatus,
} from '@/lib/firebase/firebase-server';
import type { ChatAnchor, ChatPreset } from '@/lib/firebase/firebase.types';
import { Suspense } from 'react';
import ChatAnchorCard from './chat-anchor-card';
import ChatDynamicChatInput from './chat-dynamic-chat-input';
import { ChatJumpBackPill, ChatJumpProvider } from './chat-jump';
import ChatLiveElectionCard from './chat-live-election-card';
import ChatScrollDownIndicator from './chat-scroll-down-indicator';
import ChatViewSsr from './chat-view-ssr';

type Props = {
  sessionId?: string;
  partyIds?: string[];
  initialQuestion?: string;
  prefilledQuestion?: string;
  contextId?: string;
  anchor?: ChatAnchor;
  preset?: ChatPreset;
};

async function ChatView({
  sessionId,
  partyIds,
  initialQuestion,
  prefilledQuestion,
  contextId = DEFAULT_CONTEXT_ID,
  anchor,
  preset,
}: Props) {
  const systemStatus = await getSystemStatus();
  const user = await getCurrentUser();

  return (
    <ChatJumpProvider>
      <section className="relative mx-auto flex size-full max-w-2xl flex-col overflow-hidden">
        <ChatAnchorCard />
        <Suspense
          fallback={
            <div className="flex grow flex-col items-center justify-center gap-2">
              <LoadingSpinner />
              <p className="text-center text-sm text-muted-foreground">
                Loading Chat Session...
              </p>
            </div>
          }
        >
          <ChatViewSsr
            chatSessionId={sessionId}
            partyIds={partyIds}
            initialQuestion={initialQuestion}
            prefilledQuestion={prefilledQuestion}
            contextId={contextId}
            anchor={anchor}
            preset={preset}
          />
        </Suspense>

        <div className="relative px-3 md:px-4">
          <div className="pointer-events-none absolute inset-x-0 -top-14 z-10 flex justify-center">
            <ChatJumpBackPill />
          </div>
          <ChatProlificWrapper />
          <ChatStudyWrapper />
          <ChatScrollDownIndicator />
          <ChatLiveElectionCard />
          <ChatDynamicChatInput
            initialSystemStatus={systemStatus}
            hasValidServerUser={!user?.isAnonymous}
          />
          <AiDisclaimer />
        </div>
      </section>
    </ChatJumpProvider>
  );
}

export default ChatView;
