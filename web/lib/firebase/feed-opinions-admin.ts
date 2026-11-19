import 'server-only';

import {
  ABANDONED_AFTER_DAYS,
  EMPTY_OPINION,
  OPINION_CONSENT_VERSION,
  type OpinionChange,
  type OpinionIncrements,
  type PublishedCounts,
  type ReaderActivity,
  applyIncrements,
  hasIncrements,
  isAbandoned,
  isEmptyOpinion,
  nextOpinion,
  opinionIncrements,
  publishedCounts,
  toFeedOpinion,
  toOpinionCounts,
} from '@/lib/daily/opinions';
import { type UserRecord, getAuth } from 'firebase-admin/auth';
import {
  type DocumentData,
  type DocumentReference,
  FieldValue,
  type Firestore,
  Timestamp,
} from 'firebase-admin/firestore';
import { getAdminApp, getAdminDb } from './firebase-admin-app';

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
 * `set` applies to exactly the counters named. No timestamp: the time of the
 * last change would tell an observer when one reader answered. */
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
  return { vote, positions };
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
  | { ok: true; counts: PublishedCounts }
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
    // A taken-back opinion leaves no doc, which would still record that the
    // reader engaged with the item.
    if (isEmptyOpinion(next)) {
      tx.delete(ownRef);
    } else {
      tx.set(ownRef, {
        item_id: change.itemId,
        kind: itemData.kind,
        vote: next.vote,
        positions: next.positions,
        updated_at: FieldValue.serverTimestamp(),
      });
    }
    if (hasIncrements(increments)) {
      tx.set(counts, incrementFields(increments), { merge: true });
    }
    return {
      ok: true,
      counts: publishedCounts(
        applyIncrements(toOpinionCounts(current.data()), increments),
      ),
    } as const;
  });
}

/** An item's counts as readers may see them; see `publishedCounts`. */
export async function readFeedOpinionCounts(
  itemId: string,
): Promise<PublishedCounts> {
  const snapshot = await countsRef(getAdminDb(), itemId).get();
  return publishedCounts(toOpinionCounts(snapshot.data()));
}

// Each withdrawn item takes two writes (its counts and the reader's doc), so
// a batch of this many stays well under Firestore's 500-write limit.
const WITHDRAW_CHUNK = 200;

/**
 * Withdraws the reader's consent: every opinion they gave is taken out of its
 * item's counts and deleted, and the consent itself is removed.
 *
 * The consent goes first. `applyFeedOpinion` reads the user doc in its
 * transaction, so a tap that overlaps this write retries, finds no consent
 * and is refused; the deletes then repeat until nothing is left, so an
 * opinion stored while they run is not missed.
 */
export async function withdrawFeedOpinions(uid: string): Promise<number> {
  const db = getAdminDb();
  const userRef = db.collection('users').doc(uid);
  await userRef.set(
    { feed_opinion_consent: FieldValue.delete() },
    { merge: true },
  );

  let deleted = 0;
  for (;;) {
    const page = await userRef.collection(OPINIONS).limit(WITHDRAW_CHUNK).get();
    if (page.empty) {
      return deleted;
    }
    const batch = db.batch();
    for (const doc of page.docs) {
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
    deleted += page.size;
  }
}

// Bounds one run of the retention job; the rest waits for the next run.
const RETENTION_SCAN_LIMIT = 2000;
// `getUsers` takes at most 100 identifiers per call.
const AUTH_LOOKUP_CHUNK = 100;

function readerActivity(user: UserRecord): ReaderActivity {
  const { lastRefreshTime, lastSignInTime, creationTime } = user.metadata;
  const times = [lastRefreshTime, lastSignInTime, creationTime]
    .map((time) => (time ? Date.parse(time) : Number.NaN))
    .filter(Number.isFinite);
  return {
    anonymous: user.providerData.length === 0,
    lastActiveMs: times.length > 0 ? Math.max(...times) : 0,
  };
}

/**
 * Deletes the opinions of readers past retention (see `isAbandoned`): an
 * anonymous uid is lost with the browser's storage, and with it the only way
 * to withdraw. Candidates are uids holding an opinion older than the cutoff;
 * whether they are still around is read from Auth.
 */
export async function expireAbandonedOpinions(
  now: Date,
): Promise<{ readers: number; opinions: number }> {
  const db = getAdminDb();
  const cutoffMs = now.getTime() - ABANDONED_AFTER_DAYS * 24 * 60 * 60 * 1000;
  const stale = await db
    .collectionGroup(OPINIONS)
    .where('updated_at', '<', Timestamp.fromMillis(cutoffMs))
    .select()
    .limit(RETENTION_SCAN_LIMIT)
    .get();
  const uids = [
    ...new Set(
      stale.docs
        .map((doc) => doc.ref.parent.parent?.id)
        .filter((uid): uid is string => Boolean(uid)),
    ),
  ];

  const auth = getAuth(getAdminApp());
  let readers = 0;
  let opinions = 0;
  for (let i = 0; i < uids.length; i += AUTH_LOOKUP_CHUNK) {
    const chunk = uids.slice(i, i + AUTH_LOOKUP_CHUNK);
    const { users } = await auth.getUsers(chunk.map((uid) => ({ uid })));
    const found = new Map(users.map((user) => [user.uid, user]));
    for (const uid of chunk) {
      const user = found.get(uid);
      if (isAbandoned(user ? readerActivity(user) : null, cutoffMs)) {
        opinions += await withdrawFeedOpinions(uid);
        readers += 1;
      }
    }
  }
  return { readers, opinions };
}
