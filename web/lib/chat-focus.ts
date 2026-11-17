import type { PartyDetails } from '@/lib/party-details';

/** The `focus_party_ids` stamp of a user message; nothing without a focus. */
export function focusStamp(partyIds: Iterable<string>): {
  focus_party_ids?: string[];
} {
  const ids = [...partyIds];
  return ids.length > 0 ? { focus_party_ids: ids } : {};
}

/** "SPD · CDU"; an id the context does not know stays as it is. */
export function focusLabel(
  partyIds: readonly string[],
  parties: readonly PartyDetails[] | undefined,
): string {
  return partyIds
    .map((id) => parties?.find((p) => p.party_id === id)?.name ?? id)
    .join(' · ');
}

/** The focus with `partyId` added or removed. */
export function toggleFocus(
  partyIds: readonly string[],
  partyId: string,
): string[] {
  return partyIds.includes(partyId)
    ? partyIds.filter((id) => id !== partyId)
    : [...partyIds, partyId];
}
