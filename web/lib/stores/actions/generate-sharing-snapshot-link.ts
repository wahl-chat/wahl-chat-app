import { createShareableSession } from '@/lib/firebase/firebase-admin';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const generateSharingSnapshotLink: ChatStoreActionHandlerFor<
  'generateSharingSnapshotLink'
> = (get, set) => async () => {
  const { chatSessionId, sharingSnapshot, messages } = get();

  if (!chatSessionId) return;

  if (
    sharingSnapshot &&
    messages.length === sharingSnapshot.messagesLengthAtSharing
  ) {
    return;
  }

  set((state) => {
    state.sharingSnapshot = undefined;
  });

  const { snapshot_id, messages_length_at_sharing } =
    await createShareableSession(chatSessionId);

  set((state) => {
    state.sharingSnapshot = {
      id: snapshot_id,
      messagesLengthAtSharing: messages_length_at_sharing,
    };
  });
};
