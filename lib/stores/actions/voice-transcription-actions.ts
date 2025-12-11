import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setVoiceTranscriptionPending: ChatStoreActionHandlerFor<
  'setVoiceTranscriptionPending'
> = (_get, set) => (messageId) => {
  set((state) => {
    const group = state.messages.find((g) => g.id === messageId);
    if (group) {
      group.voice_transcription = { status: 'pending' };
    }
  });
};

export const setVoiceTranscribed: ChatStoreActionHandlerFor<
  'setVoiceTranscribed'
> = (_get, set) => (groupedMessageId, messageId, transcribedText) => {
  set((state) => {
    const group = state.messages.find((g) => g.id === groupedMessageId);
    if (group) {
      group.voice_transcription = { status: 'transcribed' };

      group.messages.forEach((m) => {
        if (m.id === messageId) {
          m.content = transcribedText;
        }
      });
    }
  });
};

export const setVoiceTranscriptionError: ChatStoreActionHandlerFor<
  'setVoiceTranscriptionError'
> = (_get, set) => (groupedMessageId, error) => {
  set((state) => {
    const group = state.messages.find((g) => g.id === groupedMessageId);
    if (group) {
      group.voice_transcription = { status: 'error', error };
    }
  });
};
