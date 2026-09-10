import type { Context, ProposedQuestion } from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import { buildPartyImageUrl } from '@/lib/utils';
import Image from 'next/image';
import Link from 'next/link';

/**
 * Real questions about each live election, every one a link into a chat.
 *
 * Two things make these safe to put on the site's most-crawled page. They are
 * server-rendered anchors, so a crawler reads the German question text and can
 * follow it. And they use ?prefill= rather than ?q=: the question lands in the
 * chat input for the visitor to send, so merely following the link never
 * triggers an answer. The chat itself is noindex, so the value sits here, in
 * the landing page's own markup.
 */

const QUESTIONS_PER_ELECTION = 3;

/** The parties a sample question is addressed to, when the election has them. */
const FEATURED_PARTY_IDS = ['cdu', 'spd', 'linke', 'gruene', 'afd', 'bsw'];

const PARTIES_PER_QUESTION = 2;

export type QuestionGroup = {
  context: Context;
  questions: ProposedQuestion[];
  /** The election's own parties. Narrowed to FEATURED_PARTY_IDS here, since
   *  not every election fields all of them. */
  parties: PartyDetails[];
};

/**
 * FNV-1a with a final avalanche step. The plain multiply-and-add hash is not
 * enough here: question ids are near-identical strings ("question_1",
 * "question_2"), and without mixing the low bits barely move, so every
 * question ends up addressed to the same pair of parties.
 */
function hashString(value: string) {
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }

  hash ^= hash >>> 16;
  hash = Math.imul(hash, 0x7feb352d) >>> 0;
  hash ^= hash >>> 15;
  return hash >>> 0;
}

/**
 * Two parties for a question, varied across questions but stable for any given
 * one. Seeded from the question id rather than Math.random() because this
 * renders into cached server HTML: a per-render shuffle would change the page's
 * outgoing links every time the cache refills.
 */
function seedParties(pool: PartyDetails[], seed: string): PartyDetails[] {
  if (pool.length <= PARTIES_PER_QUESTION) return pool;

  const hash = hashString(seed);
  const first = hash % pool.length;
  const offset = 1 + ((hash >>> 8) % (pool.length - 1));

  return [pool[first], pool[(first + offset) % pool.length]];
}

/**
 * The party pairs for one election's questions.
 *
 * Seeding each question independently is fair on average but clusters badly on
 * a set this small — it put the SPD on all three Berlin questions and all three
 * in Mecklenburg-Vorpommern while never showing the Grünen at all. So a party
 * is only reused once every other one has had a turn, which with three
 * questions and six parties means each appears exactly once per election.
 *
 * Elections that field fewer parties than there are slots (Munich has four of
 * these six) fall back to the seeded pick once the pool is exhausted.
 */
function dealParties(
  pool: PartyDetails[],
  contextId: string,
  questions: ProposedQuestion[],
): PartyDetails[][] {
  const used = new Set<string>();

  return questions.map((question) => {
    const chosen: PartyDetails[] = [];

    for (const seeded of seedParties(pool, `${contextId}:${question.id}`)) {
      const isTaken = (party: PartyDetails) =>
        used.has(party.party_id) ||
        chosen.some((c) => c.party_id === party.party_id);

      const party = isTaken(seeded)
        ? (pool.find((candidate) => !isTaken(candidate)) ?? seeded)
        : seeded;

      if (!chosen.some((c) => c.party_id === party.party_id)) {
        chosen.push(party);
        used.add(party.party_id);
      }
    }

    return chosen;
  });
}

function buildSessionHref(
  contextId: string,
  question: string,
  parties: PartyDetails[],
) {
  // URLSearchParams, not interpolation: questions contain ?, & and umlauts.
  const params = new URLSearchParams({ prefill: question });
  for (const party of parties) {
    params.append('party_id', party.party_id);
  }
  return `/${contextId}/session?${params.toString()}`;
}

function PartyLogos({ parties }: { parties: PartyDetails[] }) {
  if (parties.length === 0) return null;

  return (
    // One badge overlapping the card's top-right corner, so it reads as a
    // marker on the question rather than as part of its text.
    //
    // A pill rather than round avatars: most party logos are wide wordmarks
    // (the CDU's is 4.5:1), and a circle crops them down to an illegible
    // sliver. Fixed height with auto width keeps each one proportional.
    <span className="absolute -right-2 -top-2 flex items-center gap-1 rounded-full border border-border bg-background p-1 shadow-sm">
      {parties.map((party) => (
        <span
          key={party.party_id}
          // Each logo sits on its party's own colour, the way PartyCard renders
          // them: several are white-on-transparent (the SPD's is), so on a
          // plain background they would be invisible.
          // A fixed box rather than a fixed height: the logos range from 4.5:1
          // wordmarks to square marks, so sizing by height alone would leave
          // Die Linke's a third the size of the CDU's.
          className="flex h-7 w-12 items-center justify-center rounded-full p-1"
          style={{ backgroundColor: party.background_color ?? '#ffffff' }}
        >
          <Image
            src={buildPartyImageUrl(party.party_id)}
            alt={party.name}
            width={64}
            height={32}
            className="size-full object-contain"
          />
        </span>
      ))}
    </span>
  );
}

function ElectionQuestions({ group }: { group: QuestionGroup }) {
  const { context, questions } = group;
  // Only parties this election actually fields: the session route drops any
  // party_id that is not in the context, which would silently leave a group
  // chat with one party in it.
  const partyPool = FEATURED_PARTY_IDS.flatMap(
    (id) => group.parties.filter((party) => party.party_id === id) ?? [],
  );

  const visibleQuestions = questions.slice(0, QUESTIONS_PER_ELECTION);
  const partiesByQuestion = dealParties(
    partyPool,
    context.context_id,
    visibleQuestions,
  );

  return (
    <li className="flex w-[85vw] shrink-0 snap-start flex-col gap-4 rounded-md border border-border bg-background p-4 md:w-auto md:shrink md:p-5">
      <h3 className="text-pretty font-bold text-foreground">
        <Link href={`/${context.context_id}`} className="hover:underline">
          {context.name}
        </Link>
      </h3>

      <ul className="flex flex-col gap-4">
        {visibleQuestions.map((question, index) => {
          const parties = partiesByQuestion[index];

          return (
            // pt-6 keeps the question text clear of the overlapping badge.
            <li key={question.id} className="relative">
              <Link
                href={buildSessionHref(
                  context.context_id,
                  question.content,
                  parties,
                )}
                // The target is dynamic and noindex; prefetching every one of
                // these as the section scrolls into view would render a chat
                // per question for nothing.
                prefetch={false}
                className="group flex h-full flex-col gap-1.5 rounded-md border border-border bg-background p-3 pt-6 ring-offset-background transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                {question.topic && (
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {question.topic}
                  </span>
                )}

                <span className="text-pretty text-sm font-medium group-hover:underline">
                  {question.content}
                </span>
              </Link>

              <PartyLogos parties={parties} />
            </li>
          );
        })}
      </ul>
    </li>
  );
}

function ExampleQuestions({ groups }: { groups: QuestionGroup[] }) {
  if (groups.length === 0) return null;

  return (
    // Mobile: one card per election, swiped sideways, with the next one
    // peeking so it is obvious there is more. The negative margin lets the row
    // bleed to the screen edge while the padding keeps the first and last card
    // aligned with the rest of the page. Desktop has the width for a grid, so
    // the scroller collapses into one.
    <ul className="-mx-5 flex snap-x snap-mandatory items-stretch gap-4 overflow-x-auto px-5 pb-2 [-ms-overflow-style:none] [scrollbar-width:none] md:mx-0 md:grid md:grid-cols-2 md:items-start md:overflow-x-visible md:px-0 md:pb-0 lg:grid-cols-3 [&::-webkit-scrollbar]:hidden">
      {groups.map((group) => (
        <ElectionQuestions key={group.context.context_id} group={group} />
      ))}
    </ul>
  );
}

export default ExampleQuestions;
