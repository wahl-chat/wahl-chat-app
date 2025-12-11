import { toast } from 'sonner';
import {
  type ChatStoreActionHandlerFor,
  getTtsKey,
} from '@/lib/stores/chat-store.types';

export const requestTextToSpeech: ChatStoreActionHandlerFor<
  'requestTextToSpeech'
> = (get, set) => (partyId: string, messageId: string) => {
  const { chatSessionId, localPreliminaryChatSessionId, socket, ttsState } =
    get();

  const safeSessionId = chatSessionId ?? localPreliminaryChatSessionId;

  if (!safeSessionId) {
    toast.error('Chat Session nicht gefunden.');
    return;
  }

  const key = getTtsKey(safeSessionId, partyId, messageId);
  const currentState = ttsState[key];

  if (currentState?.status === 'ready' || currentState?.status === 'loading') {
    return;
  }

  if (!socket.io?.connected) {
    toast.error('wahl.chat ist nicht verbunden.');
    return;
  }

  set((state) => {
    state.ttsState[key] = { status: 'loading' };
  });

  socket.io.requestTextToSpeech({
    session_id: safeSessionId,
    party_id: partyId,
    message_id: messageId,
  });
};

export const setTtsReady: ChatStoreActionHandlerFor<'setTtsReady'> =
  (get, set) => (partyId: string, messageId: string, audioBase64: string) => {
    const { chatSessionId, localPreliminaryChatSessionId } = get();
    const safeSessionId = chatSessionId ?? localPreliminaryChatSessionId;
    if (!safeSessionId) return;

    const key = getTtsKey(safeSessionId, partyId, messageId);
    set((state) => {
      state.ttsState[key] = { status: 'ready', audioBase64 };
    });
  };

export const setTtsError: ChatStoreActionHandlerFor<'setTtsError'> =
  (get, set) => (partyId: string, messageId: string, error: string) => {
    const { chatSessionId, localPreliminaryChatSessionId } = get();
    const safeSessionId = chatSessionId ?? localPreliminaryChatSessionId;
    if (!safeSessionId) return;

    const key = getTtsKey(safeSessionId, partyId, messageId);
    set((state) => {
      state.ttsState[key] = { status: 'error', error };
    });
  };

export const setTtsPlaying: ChatStoreActionHandlerFor<'setTtsPlaying'> =
  (get, set) => (partyId: string, messageId: string) => {
    const { chatSessionId, localPreliminaryChatSessionId, ttsState } = get();
    const safeSessionId = chatSessionId ?? localPreliminaryChatSessionId;
    if (!safeSessionId) return;

    const key = getTtsKey(safeSessionId, partyId, messageId);
    const current = ttsState[key];
    if (current?.audioBase64) {
      set((state) => {
        state.ttsState[key] = {
          status: 'playing',
          audioBase64: current.audioBase64,
        };
      });
    }
  };

export const setTtsIdle: ChatStoreActionHandlerFor<'setTtsIdle'> =
  (get, set) => (partyId: string, messageId: string) => {
    const { chatSessionId, localPreliminaryChatSessionId, ttsState } = get();
    const safeSessionId = chatSessionId ?? localPreliminaryChatSessionId;
    if (!safeSessionId) return;

    const key = getTtsKey(safeSessionId, partyId, messageId);
    const current = ttsState[key];
    if (current?.audioBase64) {
      set((state) => {
        state.ttsState[key] = {
          status: 'ready',
          audioBase64: current.audioBase64,
        };
      });
    }
  };
