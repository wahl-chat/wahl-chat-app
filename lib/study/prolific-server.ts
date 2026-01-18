'use server';

/**
 * Returns the Prolific completion code from environment variable.
 */
export async function getProlificCompletionCode(): Promise<string> {
  return process.env.PROLIFIC_COMPLETION_CODE!;
}
