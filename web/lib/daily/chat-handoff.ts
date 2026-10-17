import { MAX_SELECTABLE_PARTIES } from '@/lib/constants';
import type { DigestParliamentId } from '@/lib/firebase/firebase.types';
import { isUnaffiliated } from './hemicycle';
import { type DetailItem, itemTitle, protocolLabel } from './items';
import { sortBySeating } from './seating-order';

/** The chat context whose parties sit in each parliament (mirrors
 * `party_context_id` in the backend's `daily_digest/parliaments.py`). */
const CHAT_CONTEXTS: Record<DigestParliamentId, string> = {
  bundestag: 'bundestagswahl-2025',
  landtag_st: 'landtagswahl-sachsen-anhalt-2026',
  landtag_bw: 'landtagswahl-baden-wuerttemberg-2026',
};

function formatDate(isoDay: string): string {
  const [year, month, day] = isoDay.split('-');
  return `${day}.${month}.${year}`;
}

function itemPartyIds(item: DetailItem): string[] {
  const parties = (
    item.kind === 'vote' ? item.vote.parties : (item.section.positions ?? [])
  ).map(({ party_id }) => ({ party_id }));
  return sortBySeating(parties)
    .map((p) => p.party_id)
    .filter((id) => !isUnaffiliated(id))
    .slice(0, MAX_SELECTABLE_PARTIES);
}

/**
 * The chat has no channel for structured context, so the item travels in the
 * question itself: what was debated or voted on, where, when, and in which
 * Plenarprotokoll. A source URL would be noise in the visible question.
 */
export function contextualQuestion(item: DetailItem, question: string): string {
  const { digest } = item;
  const where = `im ${digest.parliament_name} am ${formatDate(digest.date)}`;
  const protocol = protocolLabel(digest);
  const source = protocol ? ` (Plenarprotokoll ${protocol})` : '';
  const kind = item.kind === 'vote' ? 'Zur Abstimmung' : 'Zur Debatte';
  return `${kind} „${itemTitle(item)}“ ${where}${source}: ${question.trim()}`;
}

export function feedChatHref(item: DetailItem, question: string): string {
  const params = new URLSearchParams({
    q: contextualQuestion(item, question),
  });
  for (const id of itemPartyIds(item)) {
    params.append('party_id', id);
  }
  return `/${CHAT_CONTEXTS[item.digest.parliament]}/session?${params}`;
}
