'use client';

import { getAuthHeader } from '@/lib/firebase/firebase';
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
import { useCallback, useEffect } from 'react';
import { toast } from 'sonner';
import { useChatStore } from './chat-store-provider';

type Props = {
  children: React.ReactNode;
};

type AppendBody = {
  session_id: string;
  context_id: string;
  party_ids: string[];
  user_is_logged_in: boolean;
  chat_history?: unknown[];
};

// Expose append globally so store actions can call it without prop-drilling.
// The ref is set once when the provider mounts.
let _appendFn:
  | ((message: { role: 'user'; content: string }, body?: AppendBody) => void)
  | null = null;

export function getSseChatAppend() {
  return _appendFn;
}

// Expose stop globally so store actions (cancel/watchdog paths) can abort the
// live SSE HTTP stream and stop token burn. Set once when the provider mounts.
let _stopFn: (() => void) | null = null;

export function getSseChatStop() {
  return _stopFn;
}

function SseChatProvider({ children }: Props) {
  // Bind all Zustand store actions at the top for stable refs in useChat callbacks.
  const selectRespondingParties = useChatStore(
    (state) => state.selectRespondingParties,
  );
  const streamingMessageSourcesReady = useChatStore(
    (state) => state.streamingMessageSourcesReady,
  );
  const mergeStreamingChunkPayloadForMessage = useChatStore(
    (state) => state.mergeStreamingChunkPayloadForMessage,
  );
  const updateQuickRepliesAndTitleForCurrentStreamingMessage = useChatStore(
    (state) => state.updateQuickRepliesAndTitleForCurrentStreamingMessage,
  );
  const completeStreamingMessage = useChatStore(
    (state) => state.completeStreamingMessage,
  );
  const completeProConPerspective = useChatStore(
    (state) => state.completeProConPerspective,
  );
  const resetStreamingMessageWatchdog = useChatStore(
    (state) => state.resetStreamingMessageWatchdog,
  );
  const cancelStreamingMessages = useChatStore(
    (state) => state.cancelStreamingMessages,
  );

  const { sendMessage, stop } = useChat({
    // v5: transport replaces the `api`/`streamProtocol` options. The backend
    // emits the v5 UI-message-stream (data: <json> parts) so no protocol flag
    // is needed — useChat parses it natively.
    transport: new DefaultChatTransport({
      api: '/api/chat',
      // Attach the Firebase ID token per request (async resolvable): the proxy
      // route forwards it so the backend can verify user_is_logged_in/premium
      // Resolves to {} when signed out / on token errors —
      // the request degrades gracefully to unauthenticated.
      headers: () => getAuthHeader(),
    }),
    // v5 removed `message.annotations`. Our V1 named chat events arrive as
    // custom `data-chat_event` parts and are delivered here per-event as they
    // stream (more reliable than scraping message.parts in onFinish). The inner
    // dict (part.data) still carries its own `type` discriminator.
    onData: (dataPart) => {
      if (dataPart.type !== 'data-chat_event') {
        return;
      }
      // Any received stream event proves the stream is alive — reset the
      // inactivity watchdog so long multi-party streams (up to the 180s
      // backend budget) are not wiped mid-flight.
      resetStreamingMessageWatchdog();
      const ann = (dataPart as { data: Record<string, unknown> }).data;
      const type = ann.type as string | undefined;

      if (type === 'responding_parties') {
        // V1: 'responding_parties_selected' event → selectRespondingParties
        selectRespondingParties(
          ann.session_id as string,
          ann.party_ids as string[],
        );
      } else if (type === 'sources_ready') {
        // V1: 'sources_ready' event → streamingMessageSourcesReady
        streamingMessageSourcesReady(
          ann.session_id as string,
          ann.party_id as string,
          ann.sources as Parameters<typeof streamingMessageSourcesReady>[2],
        );
      } else if (type === 'party_chunk') {
        // V1: 'party_response_chunk_ready' event for secondary parties
        mergeStreamingChunkPayloadForMessage(
          ann.session_id as string,
          ann.party_id as string,
          ann as Parameters<typeof mergeStreamingChunkPayloadForMessage>[2],
        );
      } else if (type === 'party_complete') {
        // V1: 'party_response_complete' event → completeStreamingMessage
        completeStreamingMessage(
          ann.session_id as string,
          ann.party_id as string,
          ann.complete_message as string,
        );
      } else if (type === 'quick_replies_title') {
        // V1: 'quick_replies_and_title_ready' event
        updateQuickRepliesAndTitleForCurrentStreamingMessage(
          ann.session_id as string,
          ann.quick_replies as string[],
          ann.title as string,
        );
      } else if (type === 'pro_con_result') {
        // pro-con result arriving via the main chat stream (if routed here)
        completeProConPerspective(
          ann.request_id as string,
          ann.message as Parameters<typeof completeProConPerspective>[1],
        );
      } else if (type === 'error') {
        // FIX 14: Surface mid-stream backend error parts instead of silently dropping.
        // Backend emits type-8 error annotations from generate_chat_stream's except block.
        console.error('[SseChatProvider] backend stream error:', ann.message);
        toast.error('Es ist ein Fehler aufgetreten.');
        // Clear the streaming state so loading.newMessage does not stay stuck
        // until the watchdog fires (the backend ends the stream after an error
        // part, so nothing else would ever clear it).
        cancelStreamingMessages();
      }
    },
    onError: (error) => {
      console.error('[SseChatProvider] stream error:', error);
      // Transport-level failure (network drop, proxy 5xx, ...): wipe the
      // streaming state immediately instead of leaving a frozen UI until the
      // inactivity watchdog silently clears it.
      cancelStreamingMessages();
      toast.error(
        'Die Antwort konnte nicht geladen werden. Bitte versuche es erneut.',
      );
    },
  });

  // Expose a stable append wrapper so store actions can send messages.
  const stableAppend = useCallback(
    (
      message: { role: 'user'; content: string },
      body?: AppendBody | undefined,
    ) => {
      // v5: append() → sendMessage({ text }, { body }). Signature kept stable
      // so chat-add-user-message.ts (the only caller) needs no change.
      if (body) {
        sendMessage({ text: message.content }, { body });
      } else {
        sendMessage({ text: message.content });
      }
    },
    [sendMessage],
  );

  // Register append (for chatAddUserMessage) and stop (for
  // cancelStreamingMessages / the watchdog) as an EFFECT, not in the render
  // body: render-body assignment is a side effect (StrictMode double-invokes
  // render) and was never cleared, leaving stale sendMessage/stop closures
  // reachable after navigation. The cleanup nulls both on unmount.
  useEffect(() => {
    _appendFn = stableAppend as typeof _appendFn;
    _stopFn = stop;
    return () => {
      _appendFn = null;
      _stopFn = null;
    };
  }, [stableAppend, stop]);

  return <>{children}</>;
}

export default SseChatProvider;
