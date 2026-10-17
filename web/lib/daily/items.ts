import type {
  DailyDigest,
  DigestSessionSection,
  DigestVote,
} from '@/lib/firebase/firebase.types';

/** One news item: a debate (one section of a Plenarprotokoll) or a vote. */
export type DetailItem =
  | {
      kind: 'section';
      key: string;
      digest: DailyDigest;
      section: DigestSessionSection;
    }
  | { kind: 'vote'; key: string; digest: DailyDigest; vote: DigestVote };

export type SectionItem = Extract<DetailItem, { kind: 'section' }>;
export type VoteItem = Extract<DetailItem, { kind: 'vote' }>;

// `~` never occurs in digest ids (`{parliament}_{YYYY-MM-DD}`), so keys split
// back unambiguously and stay readable in a shared `?item=` link.
export function sectionItems(digest: DailyDigest): SectionItem[] {
  return (digest.session?.sections ?? []).map((section, i) => ({
    kind: 'section',
    key: `${digest.id}~s${i}`,
    digest,
    section,
  }));
}

export function voteItems(digest: DailyDigest): VoteItem[] {
  return digest.votes.map((vote) => ({
    kind: 'vote',
    key: `${digest.id}~v${vote.poll_id}`,
    digest,
    vote,
  }));
}

export function findItem(
  digests: readonly DailyDigest[],
  key: string,
): DetailItem | undefined {
  const digest = digests.find((d) => d.id === key.split('~')[0]);
  return digest
    ? [...sectionItems(digest), ...voteItems(digest)].find((i) => i.key === key)
    : undefined;
}

/** "21/91", or "21/90, 21/91" when a sitting day spans two protocols. A vote
 * carries the protocol of the sitting it was taken in. */
export function protocolLabel(digest: DailyDigest): string | null {
  const ids = digest.session?.protocols.map((p) => p.protocol_id) ?? [];
  return ids.length > 0 ? ids.join(', ') : null;
}

// Speech citations carry the speaker's own party; positions are per Fraktion.
const FRAKTION_OF: Record<string, string> = { csu: 'cdu' };

/** The Fraktion that opened the debate. Older digests have no `opened_by`;
 * the quote's or the first cited speech's party stands in for it. */
export function openingParty(section: DigestSessionSection): string | null {
  const party =
    section.opened_by ??
    section.opening_quote?.party_id ??
    section.citations[0]?.party_id ??
    null;
  return party ? (FRAKTION_OF[party] ?? party) : null;
}

export function itemTitle(item: DetailItem): string {
  return item.kind === 'section'
    ? item.section.headline
    : item.vote.short_title;
}

export function suggestedQuestions(item: DetailItem): string[] {
  return (
    (item.kind === 'section'
      ? item.section.suggested_questions
      : item.vote.suggested_questions) ?? []
  );
}
