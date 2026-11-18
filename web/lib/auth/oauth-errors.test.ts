import { describe, expect, it } from 'bun:test';
import { oauthErrorAction } from './oauth-errors';

describe('oauthErrorAction', () => {
  it('signs in to the account that already owns the identity or email', () => {
    expect(oauthErrorAction('auth/credential-already-in-use')).toBe(
      'sign-in-with-credential',
    );
    expect(oauthErrorAction('auth/email-already-in-use')).toBe(
      'sign-in-with-credential',
    );
    expect(
      oauthErrorAction('auth/account-exists-with-different-credential'),
    ).toBe('sign-in-with-credential');
  });

  it('stays quiet when the user closes the popup', () => {
    expect(oauthErrorAction('auth/popup-closed-by-user')).toBe('ignore');
    expect(oauthErrorAction('auth/cancelled-popup-request')).toBe('ignore');
  });

  it('names a blocked popup', () => {
    expect(oauthErrorAction('auth/popup-blocked')).toBe('popup-blocked');
  });

  it('keeps the existing outcomes', () => {
    expect(oauthErrorAction('auth/provider-already-linked')).toBe(
      'already-linked',
    );
    expect(oauthErrorAction('auth/invalid-credential')).toBe(
      'invalid-credential',
    );
  });

  it('falls back to the reload message for anything else', () => {
    expect(oauthErrorAction('auth/network-request-failed')).toBe('reload');
  });
});
