import type {
  DailyDigest,
  DigestSessionSection,
  DigestVote,
  FeedEdition,
  FeedItem,
  ParliamentFeed,
} from '@/lib/firebase/firebase.types';

function toSection(
  item: FeedItem,
  facts: NonNullable<FeedItem['debate']>,
): DigestSessionSection {
  // German is the canonical text every item has.
  const content = item.content.de;
  const text = new Map(content.positions.map((p) => [p.party_id, p.text]));
  return {
    topic: item.topics[0],
    topics: item.topics,
    headline: content.headline,
    summary: content.teaser ?? '',
    positions: facts.parties.map((party) => ({
      ...party,
      position: text.get(party.party_id) ?? null,
    })),
    agenda_items: [facts.agenda_item],
    citations: facts.citations,
    video_url: facts.video_url,
    key_points: content.key_points,
    heat: facts.heat,
    debate_minutes: facts.debate_minutes,
    opening_quote: facts.opening_quote,
    opened_by: facts.opened_by,
    suggested_questions: content.suggested_questions,
    item_id: item.id,
  };
}

function toVote(
  item: FeedItem,
  facts: NonNullable<FeedItem['vote']>,
): DigestVote {
  const content = item.content.de;
  return {
    poll_id: facts.poll_id,
    title: facts.official_title,
    short_title: content.headline,
    summary: content.teaser,
    description: facts.description,
    topics: item.topics,
    outcome: facts.outcome,
    citation_url: facts.citation_url,
    parties: facts.parties,
    suggested_questions: content.suggested_questions,
    item_id: item.id,
  };
}

/** One edition as the feed shows it, in the edition's order. Retracted items
 * stay out of the feed. */
export function editionToDigest(
  edition: FeedEdition,
  items: ReadonlyMap<string, FeedItem>,
): DailyDigest {
  const sections: DigestSessionSection[] = [];
  const votes: DigestVote[] = [];
  for (const id of edition.item_ids) {
    const item = items.get(id);
    if (!item || item.status !== 'published') {
      continue;
    }
    if (item.debate) {
      sections.push(toSection(item, item.debate));
    } else if (item.vote) {
      votes.push(toVote(item, item.vote));
    }
  }
  const hasSession = sections.length > 0 || edition.protocols.length > 0;
  return {
    id: edition.id,
    parliament: edition.parliament,
    parliament_name: edition.parliament_name,
    region: edition.region,
    date: edition.date,
    votes,
    session: hasSession ? { protocols: edition.protocols, sections } : null,
  };
}

export function feedToDigests(feed: ParliamentFeed): DailyDigest[] {
  const items = new Map(feed.items.map((item) => [item.id, item]));
  return feed.editions.map((edition) => editionToDigest(edition, items));
}
