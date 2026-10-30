import ChatProlificWrapper from '@/components/chat/chat-prolific-wrapper';
import ChatStudyWrapper from '@/components/chat/chat-study-wrapper';
import AiDisclaimer from '@/components/legal/ai-disclaimer';
import LoadingSpinner from '@/components/loading-spinner';
import { DEFAULT_LOCALE } from '@/i18n/locales';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import {
  getCurrentUser,
  getSystemStatus,
} from '@/lib/firebase/firebase-server';
import { getLocale, getTranslations } from 'next-intl/server';
import { Suspense } from 'react';
import ChatDynamicChatInput from './chat-dynamic-chat-input';
import ChatScrollDownIndicator from './chat-scroll-down-indicator';
import ChatViewSsr from './chat-view-ssr';

type Props = {
  sessionId?: string;
  partyIds?: string[];
  initialQuestion?: string;
  prefilledQuestion?: string;
  contextId?: string;
};

async function ChatView({
  sessionId,
  partyIds,
  initialQuestion,
  prefilledQuestion,
  contextId = DEFAULT_CONTEXT_ID,
}: Props) {
  const systemStatus = await getSystemStatus();
  const user = await getCurrentUser();
  const t = await getTranslations('chat.view');
  const locale = await getLocale();

  return (
    <section className="relative mx-auto flex size-full max-w-2xl flex-col overflow-hidden">
      <Suspense
        fallback={
          <div className="flex grow flex-col items-center justify-center gap-2">
            <LoadingSpinner />
            <p className="text-center text-sm text-muted-foreground">
              {t('loading')}
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
        />
      </Suspense>

      <div className="relative px-3 md:px-4">
        <ChatProlificWrapper />
        <ChatStudyWrapper />
        <ChatScrollDownIndicator />
        <ChatDynamicChatInput
          initialSystemStatus={systemStatus}
          hasValidServerUser={!user?.isAnonymous}
        />
        {/* The model answers in German whatever the UI language, so readers of
            any other UI language are told before they ask. */}
        {locale !== DEFAULT_LOCALE && (
          <p className="mt-2 text-center text-xs text-muted-foreground">
            {t('answerLanguageNote')}
          </p>
        )}
        <AiDisclaimer />
      </div>
    </section>
  );
}

export default ChatView;
