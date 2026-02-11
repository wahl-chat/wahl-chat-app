'use client';

const STORAGE_KEY = 'prolific_metadata';
const MESSAGE_COUNT_KEY = 'prolific_message_count';

export interface ProlificMetadata {
  prolific_pid: string;
  study_id: string;
  session_id: string;
}

/**
 * Sanitizes a Prolific URL parameter by allowing only
 * alphanumeric characters, hyphens, and underscores,
 * and limiting length to 128 characters.
 */
function sanitizeProlificParam(value: string): string {
  return value.replace(/[^a-zA-Z0-9\-_]/g, '').slice(0, 128);
}

/**
 * Extracts Prolific metadata from URL query params.
 * Returns null if not all params are present.
 */
export function extractProlificParams(
  searchParams: URLSearchParams,
): ProlificMetadata | null {
  const prolificPid = searchParams.get('PROLIFIC_PID');
  const studyId = searchParams.get('STUDY_ID');
  const sessionId = searchParams.get('SESSION_ID');

  if (!prolificPid || !studyId || !sessionId) {
    return null;
  }

  return {
    prolific_pid: sanitizeProlificParam(prolificPid),
    study_id: sanitizeProlificParam(studyId),
    session_id: sanitizeProlificParam(sessionId),
  };
}

/**
 * Stores Prolific metadata in sessionStorage.
 */
export function storeProlificMetadata(metadata: ProlificMetadata): void {
  if (typeof window === 'undefined') return;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(metadata));
}

/**
 * Retrieves Prolific metadata from sessionStorage.
 * Returns null if not found.
 */
export function getProlificMetadata(): ProlificMetadata | null {
  if (typeof window === 'undefined') return null;

  const stored = sessionStorage.getItem(STORAGE_KEY);
  if (!stored) return null;

  try {
    return JSON.parse(stored) as ProlificMetadata;
  } catch {
    return null;
  }
}

/**
 * Clears Prolific metadata from sessionStorage.
 */
export function clearProlificMetadata(): void {
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem(STORAGE_KEY);
  sessionStorage.removeItem(MESSAGE_COUNT_KEY);
}

/**
 * Captures Prolific params from URL and stores them.
 * Call this on page mount to capture incoming study participants.
 * Returns the metadata if found, null otherwise.
 */
export function captureProlificParams(
  searchParams: URLSearchParams,
): ProlificMetadata | null {
  const metadata = extractProlificParams(searchParams);
  if (metadata) {
    storeProlificMetadata(metadata);
    return metadata;
  }
  return getProlificMetadata();
}

/**
 * Check if the current session is part of a Prolific study.
 * Checks both URL params and sessionStorage.
 */
export function isProlificStudy(): boolean {
  // Check sessionStorage first
  if (getProlificMetadata() !== null) {
    return true;
  }

  // Also check URL params directly (for initial render before useEffect runs)
  if (typeof window !== 'undefined') {
    const urlParams = new URLSearchParams(window.location.search);
    return (
      urlParams.has('PROLIFIC_PID') &&
      urlParams.has('STUDY_ID') &&
      urlParams.has('SESSION_ID')
    );
  }

  return false;
}

/**
 * Gets the total message count from the wahl-chat-session from sessionStorage.
 */
export function getWahlChatSessionMessageCount(): number {
  if (typeof window === 'undefined') return 0;

  const stored = sessionStorage.getItem(MESSAGE_COUNT_KEY);
  if (!stored) return 0;

  const count = Number.parseInt(stored, 10);
  return Number.isNaN(count) ? 0 : count;
}

/**
 * Increments the prolific message count in sessionStorage.
 * Only increments if this is a prolific study session.
 */
export function incrementWahlChatSessionMessageCount(): number {
  if (typeof window === 'undefined') return 0;
  if (!isProlificStudy()) return 0;

  const currentCount = getWahlChatSessionMessageCount();
  const newCount = currentCount + 1;
  sessionStorage.setItem(MESSAGE_COUNT_KEY, String(newCount));
  return newCount;
}

/**
 * Resets the prolific message count in sessionStorage.
 */
export function resetWahlChatSessionMessageCount(): void {
  if (typeof window === 'undefined') return;
  sessionStorage.removeItem(MESSAGE_COUNT_KEY);
}
