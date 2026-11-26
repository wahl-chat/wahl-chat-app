import type {
  ChatStoreActionHandlerFor,
  ToolStatus,
} from '@/lib/stores/chat-store.types';

/** A call's line keeps its place; its later event replaces label and state. */
export function upsertToolStatus(
  lines: readonly ToolStatus[],
  status: ToolStatus,
): ToolStatus[] {
  const at = lines.findIndex((line) => line.call_id === status.call_id);
  if (at === -1) {
    return [...lines, status];
  }
  return lines.map((line, i) => (i === at ? status : line));
}

export const updateToolStatus: ChatStoreActionHandlerFor<'updateToolStatus'> =
  (_get, set) => (sessionId, status) => {
    set((state) => {
      if (state.chatSessionId !== sessionId) return;
      if (!state.currentStreamingMessages) return;

      state.currentStreamingMessages.tool_status = upsertToolStatus(
        state.currentStreamingMessages.tool_status ?? [],
        status,
      );
    });
  };
