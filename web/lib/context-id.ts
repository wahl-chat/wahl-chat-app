/**
 * Whether a path segment has the shape of a context id: lowercase words joined
 * by hyphens, ending in a year (`bw2026`, `bundestagswahl-2025`,
 * `landtagswahl-sachsen-anhalt-2026`).
 *
 * Shape only — whether the context exists is Firestore's call. It separates a
 * stale election link, which still deserves an election page, from a path
 * that was never one (`/news`, `/foo`), which should 404 rather than land on
 * an arbitrary election.
 */
export function looksLikeContextId(segment: string): boolean {
  return /^[a-z]+(?:-[a-z]+)*-?\d{4}$/.test(segment);
}
