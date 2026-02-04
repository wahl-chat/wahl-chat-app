export const WAHL_CHAT_PARTY_ID = 'wahl-chat';
export const GROUP_PARTY_ID = 'group';

export const TENANT_ID_HEADER = 'x-tenant-id';
export const CONTEXT_ID_HEADER = 'x-context-id';

export const DEFAULT_CONTEXT_ID =
  process.env.NEXT_PUBLIC_DEFAULT_CONTEXT_ID ??
  'landtagswahl-baden-wuerttemberg-2026';

// Region to context ID mapping for geo-IP detection
export const REGION_TO_CONTEXT: Record<string, string> = {
  BW: 'landtagswahl-baden-wuerttemberg-2026', // Baden-Württemberg
  BY: 'kommunalwahl-muenchen-2026', // Bayern
  BE: 'be2026', // Berlin
  BB: 'bb2029', // Brandenburg
  HB: 'hb2027', // Bremen
  HH: 'hh2029', // Hamburg
  HE: 'he2028', // Hessen
  MV: 'mv2026', // Mecklenburg-Vorpommern
  NI: 'ni2027', // Niedersachsen
  NW: 'nw2027', // Nordrhein-Westfalen
  RP: 'rp2026', // Rheinland-Pfalz
  SL: 'sl2027', // Saarland
  SN: 'sn2029', // Sachsen
  ST: 'st2026', // Sachsen-Anhalt
  SH: 'sh2027', // Schleswig-Holstein
  TH: 'th2029', // Thüringen
};
