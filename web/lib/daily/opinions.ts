// A reader's opinions on a feed item: how they would have voted, and whether
// they agree with each Fraktion's position. Political opinions are GDPR
// Art. 9 data, so they are only ever written by the server, after an explicit
// opt-in (`feed_opinion_consent` on the user doc).

export type VoteOpinion = 'accept' | 'reject';
export type PositionOpinion = 'up' | 'down';

/** `users/{uid}/feed_opinions/{item_id}`, without its bookkeeping fields. */
export type FeedOpinion = {
  vote: VoteOpinion | null;
  positions: Record<string, PositionOpinion>;
};

/** `feed_items/{item_id}/counts/opinions`: everyone's opinions, summed. */
export type OpinionCounts = {
  vote: Record<VoteOpinion, number>;
  positions: Record<string, Record<PositionOpinion, number>>;
};

/** What one change adds to `OpinionCounts`: only the counters that move. */
export type OpinionIncrements = {
  vote: Partial<Record<VoteOpinion, number>>;
  positions: Record<string, Partial<Record<PositionOpinion, number>>>;
};

export type OpinionTarget =
  | { kind: 'vote' }
  | { kind: 'position'; partyId: string };

export type OpinionChange = {
  itemId: string;
  target: OpinionTarget;
  /** `null` takes the opinion back. */
  value: VoteOpinion | PositionOpinion | null;
  /** Set on the request the reader answered the consent sheet with „Ja". */
  consent: boolean;
};

/** Bumped when the consent text changes in substance, so a stored consent
 * shows which text it was given to. */
export const OPINION_CONSENT_VERSION = 1;

export const EMPTY_OPINION: FeedOpinion = { vote: null, positions: {} };

export const EMPTY_COUNTS: OpinionCounts = {
  vote: { accept: 0, reject: 0 },
  positions: {},
};

const VOTE_VALUES: readonly string[] = ['accept', 'reject'];
const POSITION_VALUES: readonly string[] = ['up', 'down'];

// Item ids are capped like `feed_interest`'s. Party ids become map keys in
// Firestore, so they are held to the slug alphabet.
const ITEM_ID_RE = /^[A-Za-z0-9_.~-]{1,120}$/;
const PARTY_ID_RE = /^[a-z0-9_-]{1,40}$/;

export function parseFeedOpinionBody(
  body: unknown,
): { ok: true; data: OpinionChange } | { ok: false; error: string } {
  if (!body || typeof body !== 'object') {
    return { ok: false, error: 'Invalid body' };
  }
  const record = body as Record<string, unknown>;
  const itemId = record.item_id;
  if (typeof itemId !== 'string' || !ITEM_ID_RE.test(itemId)) {
    return { ok: false, error: 'Invalid item_id' };
  }
  const value = record.value;
  let target: OpinionTarget;
  let allowed: readonly string[];
  if (record.target === 'vote') {
    target = { kind: 'vote' };
    allowed = VOTE_VALUES;
  } else if (record.target === 'position') {
    const partyId = record.party_id;
    if (typeof partyId !== 'string' || !PARTY_ID_RE.test(partyId)) {
      return { ok: false, error: 'Invalid party_id' };
    }
    target = { kind: 'position', partyId };
    allowed = POSITION_VALUES;
  } else {
    return { ok: false, error: 'Invalid target' };
  }
  if (
    value !== null &&
    !(typeof value === 'string' && allowed.includes(value))
  ) {
    return { ok: false, error: 'Invalid value' };
  }
  return {
    ok: true,
    data: {
      itemId,
      target,
      value: value as OpinionChange['value'],
      consent: record.consent === true,
    },
  };
}

/** The reader's opinion on the item once `value` is set on `target`. */
export function nextOpinion(
  previous: FeedOpinion,
  target: OpinionTarget,
  value: OpinionChange['value'],
): FeedOpinion {
  if (target.kind === 'vote') {
    return { ...previous, vote: value as VoteOpinion | null };
  }
  const positions = { ...previous.positions };
  if (value === null) {
    delete positions[target.partyId];
  } else {
    positions[target.partyId] = value as PositionOpinion;
  }
  return { ...previous, positions };
}

/** What one reader's change adds to the item's counts: −1 for the opinion
 * given up, +1 for the new one. Only the counters that move are listed. */
export function opinionIncrements(
  previous: FeedOpinion,
  next: FeedOpinion,
): OpinionIncrements {
  const increments: OpinionIncrements = { vote: {}, positions: {} };
  if (previous.vote !== next.vote) {
    if (previous.vote) {
      increments.vote[previous.vote] = -1;
    }
    if (next.vote) {
      increments.vote[next.vote] = 1;
    }
  }
  const parties = new Set([
    ...Object.keys(previous.positions),
    ...Object.keys(next.positions),
  ]);
  for (const partyId of parties) {
    const before = previous.positions[partyId];
    const after = next.positions[partyId];
    if (before === after) {
      continue;
    }
    const party: Partial<Record<PositionOpinion, number>> = {};
    if (before) {
      party[before] = -1;
    }
    if (after) {
      party[after] = 1;
    }
    increments.positions[partyId] = party;
  }
  return increments;
}

export function hasIncrements(increments: OpinionIncrements): boolean {
  return (
    Object.keys(increments.vote).length > 0 ||
    Object.keys(increments.positions).length > 0
  );
}

/** `counts` with `increments` added, as the server's increments will. */
export function applyIncrements(
  counts: OpinionCounts,
  increments: OpinionIncrements,
): OpinionCounts {
  const vote = { ...counts.vote };
  for (const [key, delta] of Object.entries(increments.vote)) {
    vote[key as VoteOpinion] += delta ?? 0;
  }
  const positions = { ...counts.positions };
  for (const [partyId, party] of Object.entries(increments.positions)) {
    const current = { ...(positions[partyId] ?? { up: 0, down: 0 }) };
    for (const [key, delta] of Object.entries(party)) {
      current[key as PositionOpinion] += delta ?? 0;
    }
    positions[partyId] = current;
  }
  return { vote, positions };
}

/** A stored counts doc, read defensively: a field that is missing or not a
 * number counts as zero. */
export function toOpinionCounts(data: unknown): OpinionCounts {
  const record = (data ?? {}) as Record<string, unknown>;
  const vote = (record.vote ?? {}) as Record<string, unknown>;
  const positions: OpinionCounts['positions'] = {};
  for (const [partyId, party] of Object.entries(
    (record.positions ?? {}) as Record<string, Record<string, unknown>>,
  )) {
    positions[partyId] = { up: count(party?.up), down: count(party?.down) };
  }
  return {
    vote: { accept: count(vote.accept), reject: count(vote.reject) },
    positions,
  };
}

/** A stored opinion doc, read defensively. */
export function toFeedOpinion(data: unknown): FeedOpinion {
  const record = (data ?? {}) as Record<string, unknown>;
  const vote =
    typeof record.vote === 'string' && VOTE_VALUES.includes(record.vote)
      ? (record.vote as VoteOpinion)
      : null;
  const positions: FeedOpinion['positions'] = {};
  for (const [partyId, value] of Object.entries(
    (record.positions ?? {}) as Record<string, unknown>,
  )) {
    if (typeof value === 'string' && POSITION_VALUES.includes(value)) {
      positions[partyId] = value as PositionOpinion;
    }
  }
  return { vote, positions };
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.max(0, value)
    : 0;
}

/** The score next to a position: agreement minus disagreement. */
export function netScore(counts: OpinionCounts, partyId: string): number {
  const party = counts.positions[partyId];
  return party ? party.up - party.down : 0;
}
