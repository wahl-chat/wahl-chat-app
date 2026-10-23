export type ShareOutcome = 'shared' | 'copied' | 'cancelled' | 'failed';

export type SharePayload = { text: string; files?: File[] };

/** The browser features sharing needs; tests pass fakes. */
export type ShareEnv = {
  share?: (data: SharePayload) => Promise<void>;
  /** Whether the share sheet takes this payload (files are not universal). */
  canShare?: (data: SharePayload) => boolean;
  writeText?: (text: string) => Promise<void>;
};

/**
 * Shares the text, with the share image where the share sheet takes files,
 * and copies the text to the clipboard where there is no share sheet.
 * 'failed' means neither worked, so the caller should show the text for the
 * player to copy by hand.
 */
export async function shareText(
  text: string,
  env: ShareEnv,
  image?: File | null,
): Promise<ShareOutcome> {
  if (env.share) {
    const withImage: SharePayload | null =
      image && env.canShare?.({ text, files: [image] })
        ? { text, files: [image] }
        : null;
    // If the image is refused, the text alone is still worth a try.
    for (const payload of withImage ? [withImage, { text }] : [{ text }]) {
      try {
        await env.share(payload);
        return 'shared';
      } catch (error) {
        // Closing the share sheet without choosing an app is not a failure.
        if (error instanceof DOMException && error.name === 'AbortError') {
          return 'cancelled';
        }
        // Any other error (the browser blocked sharing): try the next way.
      }
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
    canShare: navigator.canShare
      ? (data) => navigator.canShare(data)
      : undefined,
    writeText: navigator.clipboard?.writeText
      ? (text) => navigator.clipboard.writeText(text)
      : undefined,
  };
}

/** Fetches the share image as a file for the share sheet, or null. */
export async function fetchShareImage(
  path: string,
  fileName: string,
): Promise<File | null> {
  try {
    const response = await fetch(path);
    if (!response.ok) {
      return null;
    }
    const blob = await response.blob();
    return new File([blob], fileName, { type: 'image/png' });
  } catch {
    return null;
  }
}
