'use server';

/**
 * Returns the Prolific completion code from environment variable.
 */
export async function getProlificCompletionCode(): Promise<string> {
  const completionCode = process.env.PROLIFIC_COMPLETION_CODE;
  if (!completionCode) {
    throw new Error('PROLIFIC_COMPLETION_CODE is not set');
  }
  return completionCode;
}

/**
 * Returns the Prolific chat configuration.
 */
export async function getProlificChatConfig(): Promise<{
  minInteractions: number;
}> {
  return {
    minInteractions: Number.parseInt(
      process.env.PROLIFIC_MIN_CHAT_INTERACTIONS ?? '10',
      10,
    ),
  };
}
