import AiDisclaimer from '@/components/legal/ai-disclaimer';
import LoadingSpinner from '@/components/loading-spinner';
import {
  getCurrentUser,
  getSystemStatus,
} from '@/lib/firebase/firebase-server';
import { Suspense } from 'react';
import ChatDynamicChatInput from './chat-dynamic-chat-input';
import ChatScrollDownIndicator from './chat-scroll-down-indicator';
import ChatViewSsr from './chat-view-ssr';

type Props = {
  sessionId?: string;
  partyIds?: string[];
  initialQuestion?: string;
  hasPendingVoiceMessage?: boolean;
};

async function ChatView({
  sessionId,
  partyIds,
  initialQuestion,
  hasPendingVoiceMessage,
}: Props) {
  const systemStatus = await getSystemStatus();
  const user = await getCurrentUser();

  return (
    <section className="relative mx-auto flex size-full max-w-2xl flex-col overflow-hidden">
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
          hasPendingVoiceMessage={hasPendingVoiceMessage}
        />
      </Suspense>

      <div className="relative px-3 md:px-4">
        <ChatScrollDownIndicator />
        <ChatDynamicChatInput
          initialSystemStatus={systemStatus}
          hasValidServerUser={!user?.isAnonymous}
        />
        <AiDisclaimer />
      </div>
    </section>
  );
}

export default ChatView;
