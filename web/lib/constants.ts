export const WAHL_CHAT_PARTY_ID = 'wahl-chat';
export const GROUP_PARTY_ID = 'group';

export const TENANT_ID_HEADER = 'x-tenant-id';
export const CONTEXT_ID_HEADER = 'x-context-id';

// Fallback context for legacy deep links (/chat/{party}, /session/...) that name
// no context of their own. Everything that can resolve an election from data
// does so via lib/elections.ts instead — this constant is only reachable from
// middleware, which cannot read Firestore.
export const DEFAULT_CONTEXT_ID =
  process.env.NEXT_PUBLIC_DEFAULT_CONTEXT_ID ??
  'landtagswahl-sachsen-anhalt-2026';
