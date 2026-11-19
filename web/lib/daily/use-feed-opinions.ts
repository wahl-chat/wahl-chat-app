'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { auth, getFeedOpinion } from '@/lib/firebase/firebase';
import { useTranslations } from 'next-intl';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  EMPTY_OPINION,
  type FeedOpinion,
  type OpinionChange,
  type OpinionTarget,
  type PublishedCounts,
  nextOpinion,
  toPublishedCounts,
} from './opinions';

/** Shows the consent sheet; resolves with the reader's answer. A dismissed
 * sheet is a „Nein". */
export type AskConsent = () => Promise<boolean>;

class ConsentRequired extends Error {}

const ENDPOINT = '/api/feed-opinions';

async function authorizedFetch(
  url: string,
  init: RequestInit = {},
): Promise<Response> {
  const token = await auth.currentUser?.getIdToken();
  if (!token) {
    throw new Error('Not signed in');
  }
  return fetch(url, {
    ...init,
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${token}`,
    },
  });
}

async function postOpinion(change: OpinionChange): Promise<PublishedCounts> {
  const response = await authorizedFetch(ENDPOINT, {
    method: 'POST',
    body: JSON.stringify({
      item_id: change.itemId,
      target: change.target.kind,
      party_id:
        change.target.kind === 'position' ? change.target.partyId : undefined,
      value: change.value,
      consent: change.consent || undefined,
    }),
  });
  if (response.status === 409) {
    throw new ConsentRequired();
  }
  if (!response.ok) {
    throw new Error(`Opinion not stored (${response.status})`);
  }
  return toPublishedCounts((await response.json()).counts);
}

async function fetchOpinionCounts(itemId: string): Promise<PublishedCounts> {
  const response = await authorizedFetch(
    `${ENDPOINT}?item_id=${encodeURIComponent(itemId)}`,
  );
  if (!response.ok) {
    throw new Error(`Opinion counts not read (${response.status})`);
  }
  return toPublishedCounts((await response.json()).counts);
}

/** Withdraws consent and deletes every opinion the reader gave. */
export async function withdrawFeedOpinions(): Promise<void> {
  const response = await authorizedFetch(ENDPOINT, { method: 'DELETE' });
  if (!response.ok) {
    throw new Error(`Opinions not withdrawn (${response.status})`);
  }
}

export type FeedOpinions = {
  /** The reader's own opinion; empty until they have consented. */
  opinion: FeedOpinion;
  /** Everyone's opinions summed, withheld where too few answered; null until
   * the reader has consented and their consent is stored, so nothing is shown
   * before they opted in. */
  counts: PublishedCounts | null;
  /** Sets an opinion, or takes it back with `null`. Asks for consent first
   * if the reader has not given it. */
  choose: (target: OpinionTarget, value: OpinionChange['value']) => void;
};

/**
 * One feed item's opinions, for a view mounted per item. Changes show at
 * once and are sent in order, so the last tap is the one stored.
 */
export function useFeedOpinions(
  itemId: string | undefined,
  askConsent: AskConsent | undefined,
): FeedOpinions {
  const t = useTranslations('opinions');
  const { user, refreshUser } = useAnonymousAuth();
  const uid = user?.uid;
  const storedConsent = Boolean(user?.feed_opinion_consent);
  // „Ja" in this view: the reader's choices show at once…
  const [acceptedHere, setAcceptedHere] = useState(false);
  // …and the totals once the server has stored the consent with the first
  // opinion, so they never show a count without the reader's own vote.
  const [savedHere, setSavedHere] = useState(false);
  const optedIn = storedConsent || acceptedHere;
  const countsVisible = storedConsent || savedHere;

  const [own, setOwnState] = useState<FeedOpinion>(EMPTY_OPINION);
  const ownRef = useRef<FeedOpinion>(EMPTY_OPINION);
  const setOwn = (opinion: FeedOpinion) => {
    ownRef.current = opinion;
    setOwnState(opinion);
  };
  const [counts, setCounts] = useState<PublishedCounts | null>(null);
  // Counts local changes, so a read or response that started before the
  // latest tap does not overwrite it.
  const changes = useRef(0);
  const queue = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => {
    if (!itemId || !uid || !storedConsent) {
      return;
    }
    const started = changes.current;
    let live = true;
    getFeedOpinion(uid, itemId)
      .then((opinion) => {
        if (live && changes.current === started) {
          setOwn(opinion);
        }
      })
      .catch((error) => console.error('Failed to read opinion', error));
    return () => {
      live = false;
    };
  }, [itemId, uid, storedConsent]);

  // Read once, then from each response: not live, since a live total shows
  // the moment one reader's answer lands.
  useEffect(() => {
    if (!itemId || !uid || !countsVisible) {
      return;
    }
    const started = changes.current;
    let live = true;
    fetchOpinionCounts(itemId)
      .then((fresh) => {
        if (live && changes.current === started) {
          setCounts(fresh);
        }
      })
      .catch((error) => console.error('Failed to read opinion counts', error));
    return () => {
      live = false;
    };
  }, [itemId, uid, countsVisible]);

  const send = (
    target: OpinionTarget,
    value: OpinionChange['value'],
    consent: boolean,
  ) => {
    if (!itemId) {
      return;
    }
    const previous = ownRef.current;
    const stamp = ++changes.current;
    // The reader's own choice shows at once; the counts wait for the server,
    // which alone knows whether a target has enough answers to show.
    setOwn(nextOpinion(previous, target, value));

    queue.current = queue.current.then(async () => {
      try {
        const fresh = await postOpinion({ itemId, target, value, consent });
        if (changes.current === stamp) {
          setCounts(fresh);
        }
        if (consent) {
          setSavedHere(true);
          void refreshUser();
        }
      } catch (error) {
        console.error('Failed to store opinion', error);
        toast.error(t('saveFailed'));
        if (consent || error instanceof ConsentRequired) {
          // Consent was not stored, or was withdrawn on another device: the
          // next tap asks again.
          setAcceptedHere(false);
          setOwn(EMPTY_OPINION);
          void refreshUser();
        } else if (uid) {
          setOwn(await getFeedOpinion(uid, itemId).catch(() => previous));
        }
      }
    });
  };

  const choose: FeedOpinions['choose'] = (target, value) => {
    if (!itemId || !uid || !askConsent) {
      return;
    }
    if (optedIn) {
      send(target, value, false);
      return;
    }
    void askConsent().then((accepted) => {
      if (accepted) {
        setAcceptedHere(true);
        send(target, value, true);
      }
    });
  };

  return {
    opinion: optedIn ? own : EMPTY_OPINION,
    counts: countsVisible ? counts : null,
    choose,
  };
}
