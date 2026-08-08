export const WAHL_CHAT_PARTY_ID = 'wahl-chat';
export const GROUP_PARTY_ID = 'group';

export const TENANT_ID_HEADER = 'x-tenant-id';
export const CONTEXT_ID_HEADER = 'x-context-id';

// Last-resort context for legacy deep links (/chat/{party}, /session/...) that
// name no context of their own and whose region resolves to no live election.
// Everything that can resolve an election from data does so via lib/elections.ts
// instead — this constant is only reachable from middleware, which cannot read
// Firestore.
export const DEFAULT_CONTEXT_ID =
  process.env.NEXT_PUBLIC_DEFAULT_CONTEXT_ID ??
  'landtagswahl-sachsen-anhalt-2026';

// Geo-IP routing cannot query Firestore while choosing the first redirect.
// Only regions with an existing context belong here; a missing context costs
// an extra redirect via /[contextId].
export const REGION_CONTEXTS: Record<
  string,
  { contextId: string; electionDate: string }
> = {
  BE: {
    contextId: 'abgeordnetenhauswahl-berlin-2026',
    electionDate: '2026-09-20',
  },
  BW: {
    contextId: 'landtagswahl-baden-wuerttemberg-2026',
    electionDate: '2026-03-08',
  },
  BY: {
    contextId: 'kommunalwahl-muenchen-2026',
    electionDate: '2026-03-08',
  },
  MV: {
    contextId: 'landtagswahl-mecklenburg-vorpommern-2026',
    electionDate: '2026-09-20',
  },
  RP: {
    contextId: 'landtagswahl-rheinland-pfalz-2026',
    electionDate: '2026-03-22',
  },
  ST: {
    contextId: 'landtagswahl-sachsen-anhalt-2026',
    electionDate: '2026-09-06',
  },
};
