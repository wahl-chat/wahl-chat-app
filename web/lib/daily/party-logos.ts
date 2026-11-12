import type {
  DigestParliamentId,
  DigestPartyPosition,
} from '@/lib/firebase/firebase.types';

const UNION = 'cdu_csu';

/** Parties a parliament shows under another logo. In the Bundestag `cdu` is
 * the joint Fraktion of CDU and CSU, which the feed job already names
 * "CDU/CSU" (`name_overrides` in ingestion/src/ingestion/feed/parliaments.py);
 * in a Landtag the CDU stands alone, and in Bavaria the CSU does. */
const LOGO_OVERRIDES: Partial<
  Record<DigestParliamentId, Record<string, string>>
> = {
  bundestag: { cdu: UNION },
};

/** The logo a party is shown with in `parliament`'s feed, for
 * `buildPartyImageUrl`. */
export function feedLogoId(
  parliament: DigestParliamentId,
  partyId: string,
): string {
  return LOGO_OVERRIDES[parliament]?.[partyId] ?? partyId;
}

/** The logo on a speaker's badge: their own party where the Fraktion joins
 * two. A Union speaker is CDU or CSU, as their profile says; until it has
 * loaded, or without one, the badge shows the Fraktion's logo. */
export function speakerLogoId(
  party: DigestPartyPosition,
  partei?: string | null,
): string {
  const logo = party.logo_id ?? party.party_id;
  if (logo !== UNION) {
    return logo;
  }
  const own = partei?.trim().toUpperCase();
  return own === 'CDU' ? 'cdu' : own === 'CSU' ? 'csu' : logo;
}

/** The party a speaker's badge names, matching its logo: their own party
 * where `speakerLogoId` shows it, else the Fraktion. */
export function speakerPartyLabel(
  party: DigestPartyPosition,
  partei?: string | null,
): string {
  const own =
    speakerLogoId(party, partei) !== (party.logo_id ?? party.party_id);
  return own && partei ? partei.trim() : party.party_name;
}
