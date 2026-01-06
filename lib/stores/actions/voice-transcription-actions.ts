import {
  updateVoiceTranscription,
  updateVoiceTranscriptionError,
} from '@/lib/firebase/firebase';
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
> = (get, set) => (groupedMessageId, messageId, transcribedText) => {
  const sessionId = get().chatSessionId;

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

  if (sessionId) {
    updateVoiceTranscription(
      sessionId,
      groupedMessageId,
      messageId,
      transcribedText,
    ).catch((error) => {
      console.error('Failed to update voice transcription in Firebase:', error);
    });
  }
};

export const setVoiceTranscriptionError: ChatStoreActionHandlerFor<
  'setVoiceTranscriptionError'
> = (get, set) => (groupedMessageId, error) => {
  const sessionId = get().chatSessionId;

  set((state) => {
    const group = state.messages.find((g) => g.id === groupedMessageId);
    if (group) {
      group.voice_transcription = { status: 'error', error };
    }
  });

  if (sessionId) {
    updateVoiceTranscriptionError(sessionId, groupedMessageId, error).catch(
      (firebaseError) => {
        console.error(
          'Failed to update voice transcription error in Firebase:',
          firebaseError,
        );
      },
    );
  }
};
