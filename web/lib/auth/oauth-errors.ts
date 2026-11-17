export type OAuthErrorAction =
  | 'sign-in-with-credential'
  | 'already-linked'
  | 'invalid-credential'
  | 'popup-blocked'
  | 'ignore'
  | 'reload';

/**
 * What the login form does with a failed sign-in or link.
 *
 * Every visitor holds an anonymous session, so OAuth first tries to link the
 * provider to it. When the provider's identity or email already belongs to
 * another account, the error carries the provider credential, and signing in
 * with it switches to the account that owns it.
 */
export function oauthErrorAction(code: string): OAuthErrorAction {
  switch (code) {
    case 'auth/credential-already-in-use':
    case 'auth/email-already-in-use':
    case 'auth/account-exists-with-different-credential':
      return 'sign-in-with-credential';
    case 'auth/provider-already-linked':
      return 'already-linked';
    case 'auth/invalid-credential':
      return 'invalid-credential';
    case 'auth/popup-blocked':
      return 'popup-blocked';
    // The user closed the window, or a second click replaced the first popup.
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request':
      return 'ignore';
    default:
      return 'reload';
  }
}
