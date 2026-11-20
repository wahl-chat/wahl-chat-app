import { describe, expect, it } from 'bun:test';
import { isAbgeordnetenwatch } from './source';

describe('isAbgeordnetenwatch', () => {
  it('accepts the site and its subdomains', () => {
    expect(isAbgeordnetenwatch('https://abgeordnetenwatch.de/x')).toBe(true);
    expect(isAbgeordnetenwatch('https://www.abgeordnetenwatch.de/x')).toBe(
      true,
    );
  });

  it('rejects look-alike hosts', () => {
    expect(isAbgeordnetenwatch('https://evil-abgeordnetenwatch.de/')).toBe(
      false,
    );
    expect(isAbgeordnetenwatch('https://abgeordnetenwatch.de.evil.com/')).toBe(
      false,
    );
  });

  it('rejects a malformed URL without throwing', () => {
    expect(isAbgeordnetenwatch('not a url')).toBe(false);
    expect(isAbgeordnetenwatch('')).toBe(false);
  });
});
