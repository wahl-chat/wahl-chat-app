import { afterEach, beforeEach, describe, expect, it } from 'bun:test';
import {
  captureStudyOverride,
  clearStudyOverride,
  readStudyOverride,
} from './variant-override';

// jsdom is not configured for this suite, so stand up the two browser globals
// the module touches. sessionStorage is per-tab in a real browser; a plain Map
// is an accurate enough stand-in for these assertions.
function setSearch(search: string): void {
  // @ts-expect-error - minimal window stub for the URL read
  globalThis.window = { location: { search } };
}

beforeEach(() => {
  const store = new Map<string, string>();
  // @ts-expect-error - minimal sessionStorage stub
  globalThis.sessionStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => store.set(k, v),
    removeItem: (k: string) => store.delete(k),
  };
  setSearch('');
});

afterEach(() => {
  // @ts-expect-error - tear the stubs down so other suites see a clean global
  globalThis.window = undefined;
  // @ts-expect-error - same teardown for the storage stub
  globalThis.sessionStorage = undefined;
});

describe('readStudyOverride', () => {
  it('maps each token to its variant', () => {
    setSearch('?sg=a');
    expect(readStudyOverride()).toEqual({
      variant: 'control',
      participation: 'experimental',
      consent: 'accepted',
      cohort: 'control',
    });

    setSearch('?sg=b');
    expect(readStudyOverride()?.cohort).toBe('manipulation');

    setSearch('?sg=x');
    const declined = readStudyOverride();
    expect(declined?.consent).toBe('declined');
    expect(declined?.participation).toBe('regular');
    // A non-participant has no arm.
    expect(declined?.cohort).toBeUndefined();
  });

  it('ignores an unknown or absent token', () => {
    setSearch('?sg=zzz');
    expect(readStudyOverride()).toBeUndefined();

    setSearch('');
    expect(readStudyOverride()).toBeUndefined();
  });

  it('does not write anything', () => {
    setSearch('?sg=b');
    readStudyOverride();
    setSearch('');
    expect(readStudyOverride()).toBeUndefined();
  });
});

describe('captureStudyOverride', () => {
  it('persists the token so it survives a navigation that drops the query', () => {
    setSearch('?sg=b');
    expect(captureStudyOverride()?.cohort).toBe('manipulation');

    setSearch('');
    expect(readStudyOverride()?.cohort).toBe('manipulation');
  });

  it('lets the URL win over a stored token', () => {
    setSearch('?sg=a');
    captureStudyOverride();

    setSearch('?sg=b');
    expect(captureStudyOverride()?.cohort).toBe('manipulation');
  });

  it('clears the stored override on the reset token', () => {
    setSearch('?sg=b');
    captureStudyOverride();

    setSearch('?sg=off');
    expect(captureStudyOverride()).toBeUndefined();

    setSearch('');
    expect(readStudyOverride()).toBeUndefined();
  });

  it('leaves no override after an explicit clear', () => {
    setSearch('?sg=a');
    captureStudyOverride();
    clearStudyOverride();

    setSearch('');
    expect(readStudyOverride()).toBeUndefined();
  });

  // Prolific participants are in a different study; enrolling them here would
  // corrupt both datasets.
  it('never overrides a Prolific participant', () => {
    setSearch('?sg=b&PROLIFIC_PID=p1&STUDY_ID=s1&SESSION_ID=x1');
    expect(readStudyOverride()).toBeUndefined();
    expect(captureStudyOverride()).toBeUndefined();
  });
});
