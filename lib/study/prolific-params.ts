'use client';

const STORAGE_KEY = 'prolific_metadata';

export interface ProlificMetadata {
  prolific_pid: string;
  study_id: string;
  session_id: string;
}

/**
 * Extracts Prolific metadata from URL query params.
 * Returns null if not all params are present.
 */
export function extractProlificParams(
  searchParams: URLSearchParams
): ProlificMetadata | null {
  const prolificPid = searchParams.get('PROLIFIC_PID');
  const studyId = searchParams.get('STUDY_ID');
  const sessionId = searchParams.get('SESSION_ID');

  if (!prolificPid || !studyId || !sessionId) {
    return null;
  }

  console.log('Prolific params found:', { prolificPid, studyId, sessionId });

  return {
    prolific_pid: prolificPid,
    study_id: studyId,
    session_id: sessionId,
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
}

/**
 * Captures Prolific params from URL and stores them.
 * Call this on page mount to capture incoming study participants.
 * Returns the metadata if found, null otherwise.
 */
export function captureProlificParams(
  searchParams: URLSearchParams
): ProlificMetadata | null {
  const metadata = extractProlificParams(searchParams);
  if (metadata) {
    storeProlificMetadata(metadata);
    return metadata;
  }
  return getProlificMetadata();
}
