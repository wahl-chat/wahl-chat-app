import { describe, expect, it } from 'bun:test';
import { splitLocalePrefix } from './locale-path';

describe('splitLocalePrefix', () => {
  it('leaves German paths, which carry no prefix, as they are', () => {
    expect(splitLocalePrefix('/session/abc')).toEqual({
      prefix: '',
      path: '/session/abc',
    });
    expect(splitLocalePrefix('/')).toEqual({ prefix: '', path: '/' });
  });

  it('splits a non-default language off', () => {
    expect(splitLocalePrefix('/en/session/abc')).toEqual({
      prefix: '/en',
      path: '/session/abc',
    });
    expect(splitLocalePrefix('/en')).toEqual({ prefix: '/en', path: '/' });
  });

  it('does not mistake an election id or the default locale for a prefix', () => {
    expect(splitLocalePrefix('/landtagswahl-sachsen-anhalt-2026')).toEqual({
      prefix: '',
      path: '/landtagswahl-sachsen-anhalt-2026',
    });
    expect(splitLocalePrefix('/english')).toEqual({
      prefix: '',
      path: '/english',
    });
    expect(splitLocalePrefix('/de/how-to').prefix).toBe('');
  });
});
