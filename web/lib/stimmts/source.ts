/**
 * Whether a puzzle's source is Abgeordnetenwatch, which is shown by its logo
 * rather than its name. The host is compared exactly (or as a subdomain), so a
 * look-alike domain never borrows the logo. A malformed URL is simply not it:
 * the footer must not throw over content data.
 */
export function isAbgeordnetenwatch(url: string): boolean {
  try {
    const { hostname } = new URL(url);
    return (
      hostname === 'abgeordnetenwatch.de' ||
      hostname.endsWith('.abgeordnetenwatch.de')
    );
  } catch {
    return false;
  }
}
