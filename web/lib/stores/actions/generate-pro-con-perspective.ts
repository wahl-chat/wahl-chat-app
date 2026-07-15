import { getAuthHeader } from '@/lib/firebase/firebase';
import { scrollMessageBottomInView } from '@/lib/scroll-utils';
import type { StreamingMessage } from '@/lib/socket.types';
import type {
  ChatStoreActionHandlerFor,
  MessageItem,
} from '@/lib/stores/chat-store.types';
import { toast } from 'sonner';

export const generateProConPerspective: ChatStoreActionHandlerFor<
  'generateProConPerspective'
> =
  (get, set) =>
  async (partyId: string, message: MessageItem | StreamingMessage) => {
    const { chatSessionId, messages, contextId, completeProConPerspective } =
      get();

    if (!chatSessionId) return;

    // SSE model: no socket connectivity check needed — each request is a
    // fresh HTTP POST to /api/pro-con (D-05).

    const indexOfProConPerspectiveMessage = messages.findIndex((m) =>
      m.messages.find((m) => m.id === message.id),
    );

    set((state) => {
      state.loading.proConPerspective = message.id;
      state.clickedProConButton = true;
    });

    if (indexOfProConPerspectiveMessage === -1) return;

    const lastUserMessageBeforeProConPerspective = messages
      .slice(0, indexOfProConPerspectiveMessage)
      .findLast((m) => m.role === 'user');

    if (!lastUserMessageBeforeProConPerspective || !message.content) return;

    try {
      // SSE replacement: use fetch + ReadableStream for the pro-con stream.
      // Pro-con is NOT a useChat turn — it is a separate SSE stream consumed
      // directly (RESEARCH.md Pattern, D-05).
      const response = await fetch('/api/pro-con', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          // Firebase ID token when signed in ({} otherwise) — the proxy route
          // forwards it so the backend can verify auth claims (A3 contract).
          ...(await getAuthHeader()),
        },
        body: JSON.stringify({
          request_id: message.id,
          party_id: partyId,
          last_assistant_message: message.content,
          last_user_message:
            lastUserMessageBeforeProConPerspective.messages[0].content,
          context_id: contextId,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Pro-con request failed: ${response.status}`);
      }

      // Parse the SSE response via ReadableStream.
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      // Track whether a result ever arrived: the backend error path is
      // HTTP 200 + an `error` annotation, and a stream can also end without
      // any result — both must clear the spinner (loading.proConPerspective).
      let receivedResult = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const payload = line.slice(5).trim();
          if (payload === '[DONE]') break;

          if (payload.startsWith('8')) {
            try {
              const annotation = JSON.parse(payload.slice(1)) as Record<
                string,
                unknown
              >;
              if (annotation.type === 'pro_con_result') {
                // V1: 'pro_con_perspective_complete' → completeProConPerspective
                receivedResult = true;
                completeProConPerspective(
                  annotation.request_id as string,
                  annotation.message as MessageItem,
                );
              } else if (annotation.type === 'error') {
                console.error('[pro-con] server error:', annotation.message);
                toast.error('Fehler beim Laden der Pro/Contra-Perspektive.');
                // Server-emitted error: stop the spinner (only `catch` cleared
                // it before, so an HTTP-200 error left it spinning forever).
                set((state) => {
                  state.loading.proConPerspective = undefined;
                });
              }
            } catch {
              // Malformed annotation — skip
            }
          }
        }
      }

      // Stream ended without a pro_con_result (and without an explicit error
      // annotation): clear the spinner so it cannot spin forever.
      if (!receivedResult) {
        set((state) => {
          state.loading.proConPerspective = undefined;
        });
      }
    } catch (error) {
      console.error('[generateProConPerspective] error:', error);
      toast.error('Fehler beim Laden der Pro/Contra-Perspektive.');

      set((state) => {
        state.loading.proConPerspective = undefined;
      });
      return;
    }

    await new Promise((resolve) => setTimeout(resolve, 10));

    scrollMessageBottomInView(message.id);
  };
