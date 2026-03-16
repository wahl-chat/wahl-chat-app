'use server';

/**
 * Returns the Prolific completion code from environment variable.
 * Returns null if not configured.
 */
export async function getProlificCompletionCode(): Promise<string | null> {
  return process.env.PROLIFIC_COMPLETION_CODE ?? null;
}

/**
 * Returns the Prolific Wahl Chat Session configuration.
 */
export async function getProlificWahlChatSessionConfig(): Promise<{
  minInteractions: number;
}> {
  return {
    minInteractions: Number.parseInt(
      process.env.PROLIFIC_MIN_CHAT_INTERACTIONS ?? '10',
    ),
  };
}
