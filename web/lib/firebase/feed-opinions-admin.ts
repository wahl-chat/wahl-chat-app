import 'server-only';

import {
  EMPTY_OPINION,
  OPINION_CONSENT_VERSION,
  type OpinionChange,
  type OpinionCounts,
  type OpinionIncrements,
  applyIncrements,
  hasIncrements,
  nextOpinion,
  opinionIncrements,
  toFeedOpinion,
  toOpinionCounts,
} from '@/lib/daily/opinions';
import {
  type DocumentData,
  type DocumentReference,
  FieldValue,
  type Firestore,
} from 'firebase-admin/firestore';
import { getAdminDb } from './firebase-admin-app';

const OPINIONS = 'feed_opinions';

// The counts sit in a subcollection of the item, not on the item: the feed
// job rewrites `feed_items/{id}` whole on every rebuild, which would wipe
// them, and the item doc is cached for the feed while the counts are read live.
function countsRef(db: Firestore, itemId: string): DocumentReference {
  return db
    .collection('feed_items')
    .doc(itemId)
    .collection('counts')
    .doc('opinions');
}

function opinionRef(
  db: Firestore,
  uid: string,
  itemId: string,
): DocumentReference {
  return db.collection('users').doc(uid).collection(OPINIONS).doc(itemId);
}

/** The increments as a nested map of `FieldValue.increment`s, which a merged
 * `set` applies to exactly the counters named. */
function incrementFields(increments: OpinionIncrements) {
  const vote = Object.fromEntries(
    Object.entries(increments.vote).map(([k, d]) => [
      k,
      FieldValue.increment(d ?? 0),
    ]),
  );
  const positions = Object.fromEntries(
    Object.entries(increments.positions).map(([partyId, party]) => [
      partyId,
      Object.fromEntries(
        Object.entries(party).map(([k, d]) => [
          k,
          FieldValue.increment(d ?? 0),
        ]),
      ),
    ]),
  );
  return { vote, positions, updated_at: FieldValue.serverTimestamp() };
}

/** Whether the item takes this opinion: a vote on a vote, a position of a
 * Fraktion whose position the item states. Anything else would count
 * opinions on things no reader was shown. */
function targetsItem(item: DocumentData, change: OpinionChange): boolean {
  if (item.status !== 'published') {
    return false;
  }
  if (change.target.kind === 'vote') {
    return item.kind === 'vote';
  }
  const partyId = change.target.partyId;
  const positions: unknown = item.content?.de?.positions;
  return (
    item.kind === 'debate' &&
    Array.isArray(positions) &&
    positions.some(
      (p) =>
        p?.party_id === partyId && typeof p.text === 'string' && p.text !== '',
    )
  );
}

export type ApplyOpinionResult =
  | { ok: true; counts: OpinionCounts }
  | { ok: false; error: 'not_found' | 'consent_required' };

/**
 * Stores one reader's change and moves the item's counts by exactly that
 * change, in one transaction: the previous opinion is read inside it, so two
 * taps in flight cannot both count.
 */
export async function applyFeedOpinion(
  uid: string,
  change: OpinionChange,
): Promise<ApplyOpinionResult> {
  const db = getAdminDb();
  const itemRef = db.collection('feed_items').doc(change.itemId);
  const userRef = db.collection('users').doc(uid);
  const ownRef = opinionRef(db, uid, change.itemId);
  const counts = countsRef(db, change.itemId);

  return db.runTransaction(async (tx) => {
    const [item, user, own, current] = await tx.getAll(
      itemRef,
      userRef,
      ownRef,
      counts,
    );
    const itemData = item.data();
    if (!itemData || !targetsItem(itemData, change)) {
      return { ok: false, error: 'not_found' } as const;
    }
    const consented = Boolean(user.data()?.feed_opinion_consent);
    if (!consented && !change.consent) {
      return { ok: false, error: 'consent_required' } as const;
    }

    const previous = own.exists ? toFeedOpinion(own.data()) : EMPTY_OPINION;
    const next = nextOpinion(previous, change.target, change.value);
    const increments = opinionIncrements(previous, next);

    if (!consented) {
      tx.set(
        userRef,
        {
          feed_opinion_consent: {
            version: OPINION_CONSENT_VERSION,
            given_at: FieldValue.serverTimestamp(),
          },
        },
        { merge: true },
      );
    }
    tx.set(ownRef, {
      item_id: change.itemId,
      kind: itemData.kind,
      vote: next.vote,
      positions: next.positions,
      updated_at: FieldValue.serverTimestamp(),
    });
    if (hasIncrements(increments)) {
      tx.set(counts, incrementFields(increments), { merge: true });
    }
    return {
      ok: true,
      counts: applyIncrements(toOpinionCounts(current.data()), increments),
    } as const;
  });
}

// Each withdrawn item takes two writes (its counts and the reader's doc), so
// a batch of this many stays well under Firestore's 500-write limit.
const WITHDRAW_CHUNK = 200;

/**
 * Withdraws the reader's consent: every opinion they gave is taken out of its
 * item's counts and deleted, and the consent itself is removed.
 */
export async function withdrawFeedOpinions(uid: string): Promise<number> {
  const db = getAdminDb();
  const userRef = db.collection('users').doc(uid);
  const own = await userRef.collection(OPINIONS).get();

  for (let i = 0; i < own.docs.length; i += WITHDRAW_CHUNK) {
    const batch = db.batch();
    for (const doc of own.docs.slice(i, i + WITHDRAW_CHUNK)) {
      const increments = opinionIncrements(
        toFeedOpinion(doc.data()),
        EMPTY_OPINION,
      );
      if (hasIncrements(increments)) {
        batch.set(countsRef(db, doc.id), incrementFields(increments), {
          merge: true,
        });
      }
      batch.delete(doc.ref);
    }
    await batch.commit();
  }
  await userRef.set(
    { feed_opinion_consent: FieldValue.delete() },
    { merge: true },
  );
  return own.size;
}
