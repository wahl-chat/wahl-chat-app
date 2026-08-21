export const WAHL_CHAT_PARTY_ID = 'wahl-chat';
export const GROUP_PARTY_ID = 'group';

export const TENANT_ID_HEADER = 'x-tenant-id';
export const CONTEXT_ID_HEADER = 'x-context-id';

// The next upcoming election. Kept static for now; deriving it from the context
// dates is tracked separately.
export const DEFAULT_CONTEXT_ID =
  process.env.NEXT_PUBLIC_DEFAULT_CONTEXT_ID ??
  'landtagswahl-sachsen-anhalt-2026';

// Region to context ID mapping for geo-IP detection. Only regions with a context
// that actually exists belong here — an unmapped region falls through to
// DEFAULT_CONTEXT_ID in a single redirect, whereas mapping it to a missing
// context costs an extra hop via /[contextId]'s redirect.
export const REGION_TO_CONTEXT: Record<string, string> = {
  BE: 'abgeordnetenhauswahl-berlin-2026', // Berlin
  BW: 'landtagswahl-baden-wuerttemberg-2026', // Baden-Württemberg
  BY: 'kommunalwahl-muenchen-2026', // Bayern
  MV: 'landtagswahl-mecklenburg-vorpommern-2026', // Mecklenburg-Vorpommern
  RP: 'landtagswahl-rheinland-pfalz-2026', // Rheinland-Pfalz
  ST: 'landtagswahl-sachsen-anhalt-2026', // Sachsen-Anhalt
};
