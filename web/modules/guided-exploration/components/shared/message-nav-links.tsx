'use client';

import SkipLink from '@/components/skip-link';

/** Stable heading id for a message in the leaf side-chat transcript. */
export const leafMessageHeadingId = (messageId: string) =>
  `leaf-msg-${messageId}`;

/** Stable heading id for a message in the main exploration transcript. */
export const chatMessageHeadingId = (messageId: string) =>
  `chat-msg-${messageId}`;

interface MessageNavLinksProps {
  /**
   * Heading id of the next message in the transcript. When set, a "jump to
   * next message" link is rendered so SR users can skip past the (often long)
   * source list to the next turn instead of arrowing through every citation.
   */
  nextHeadingId?: string | null;
  /**
   * Full link text for the next-message link, describing what comes next
   * (e.g. "Zur nächsten Antwort der KI springen"). Defaults to a generic
   * phrasing when omitted.
   */
  nextLabel?: string;
  /** id of the composer textarea, focused by the "jump to input" link. */
  inputId: string;
  /** Full link text for the jump-to-composer link. */
  inputLabel: string;
}

/** Move focus to an element by id without touching the URL hash. */
function focusElementById(id: string) {
  document.getElementById(id)?.focus();
}

/**
 * sr-only skip-links rendered *before* a message's source list: one to the
 * next message, one to the composer. Both use preventDefault + programmatic
 * focus rather than letting the browser act on the href — inside the leaf
 * `Sheet` a real hash change trips the history-back interception (closing the
 * leaf) and pollutes the URL, so the href is navigation semantics only.
 */
export function MessageNavLinks({
  nextHeadingId,
  nextLabel,
  inputId,
  inputLabel,
}: MessageNavLinksProps) {
  return (
    <>
      {nextHeadingId && (
        <SkipLink
          href={`#${nextHeadingId}`}
          onClick={(e) => {
            e.preventDefault();
            focusElementById(nextHeadingId);
          }}
        >
          {nextLabel ?? 'Zur nächsten Nachricht springen'}
        </SkipLink>
      )}
      <SkipLink
        href={`#${inputId}`}
        onClick={(e) => {
          e.preventDefault();
          focusElementById(inputId);
        }}
      >
        {inputLabel}
      </SkipLink>
    </>
  );
}
