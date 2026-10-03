export type ShareOutcome = 'shared' | 'copied' | 'cancelled' | 'failed';

/** The browser features sharing needs; tests pass fakes. */
export type ShareEnv = {
  share?: (data: { text: string }) => Promise<void>;
  writeText?: (text: string) => Promise<void>;
};

/**
 * Shares the text with the phone's share sheet where there is one, and copies
 * it to the clipboard everywhere else. 'failed' means neither worked, so the
 * caller should show the text for the player to copy by hand.
 */
export async function shareText(
  text: string,
  env: ShareEnv,
): Promise<ShareOutcome> {
  if (env.share) {
    try {
      await env.share({ text });
      return 'shared';
    } catch (error) {
      // Closing the share sheet without choosing an app is not a failure.
      if (error instanceof DOMException && error.name === 'AbortError') {
        return 'cancelled';
      }
      // Any other error (the browser blocked sharing): try copying instead.
    }
  }

  if (env.writeText) {
    try {
      await env.writeText(text);
      return 'copied';
    } catch {
      // Clipboard access denied; fall through to 'failed'.
    }
  }
  return 'failed';
}

export function browserShareEnv(): ShareEnv {
  if (typeof navigator === 'undefined') {
    return {};
  }
  return {
    share: navigator.share ? (data) => navigator.share(data) : undefined,
    writeText: navigator.clipboard?.writeText
      ? (text) => navigator.clipboard.writeText(text)
      : undefined,
  };
}
