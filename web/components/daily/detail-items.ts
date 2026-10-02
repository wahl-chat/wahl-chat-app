import type { FeedDay } from '@/lib/daily/feed';
import { matchesTopics, splitSections } from '@/lib/daily/topics';
import type { DailyDigest, DigestVote } from '@/lib/firebase/firebase.types';

export type DetailItem =
  | { kind: 'session'; key: string; digest: DailyDigest }
  | { kind: 'vote'; key: string; digest: DailyDigest; vote: DigestVote };

export type DigestView = {
  digest: DailyDigest;
  /** False when the topic filter leaves this parliament nothing to show. */
  visible: boolean;
  votes: DigestVote[];
  hiddenCount: number;
};

/** What a digest shows under the current topic filter. */
export function viewDigest(
  digest: DailyDigest,
  selectedTopics: string[],
): DigestView {
  const votes = digest.votes.filter((v) =>
    matchesTopics(v.topics, selectedTopics),
  );
  const sections = digest.session
    ? splitSections(digest.session.sections, selectedTopics)
    : { visible: [], hidden: [] };
  return {
    digest,
    visible:
      (digest.session !== null && selectedTopics.length === 0) ||
      sections.visible.length > 0 ||
      votes.length > 0,
    votes,
    hiddenCount: digest.votes.length - votes.length + sections.hidden.length,
  };
}

/**
 * Everything one day offers, in on-page order, so the detail dialog can step
 * through a day without closing. A session stays reachable even when the
 * filter hides all of its sections, because its card still links to it.
 */
export function detailItems(views: DigestView[]): DetailItem[] {
  return views.flatMap((view) => [
    ...(view.digest.session && view.visible
      ? [
          {
            kind: 'session' as const,
            key: `${view.digest.id}:session`,
            digest: view.digest,
          },
        ]
      : []),
    ...view.votes.map((vote) => ({
      kind: 'vote' as const,
      key: `${view.digest.id}:${vote.poll_id}`,
      digest: view.digest,
      vote,
    })),
  ]);
}

export function viewDay(day: FeedDay, selectedTopics: string[]) {
  return day.digests.map((digest) => viewDigest(digest, selectedTopics));
}
