/** Stable heading id for a message in the leaf side-chat transcript. */
export const leafMessageHeadingId = (messageId: string) =>
  `leaf-msg-${messageId}`;

/** Stable heading id for a message in the main exploration transcript. */
export const chatMessageHeadingId = (messageId: string) =>
  `chat-msg-${messageId}`;
