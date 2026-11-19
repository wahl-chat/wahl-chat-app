import { CARD_SURFACE, FOCUS_RING } from '@/components/daily/card-styles';
import {
  feedDate,
  formatDate,
  shortDay,
  voteDateShort,
} from '@/lib/stimmts/labels';
import { MAX_SCORE } from '@/lib/stimmts/share-image';
import { cn } from '@/lib/utils';
import type { ReactNode, Ref } from 'react';
import PartyTile from './party-tile';
import StimmtsLogo from './stimmts-logo';
import { Verdict } from './verdict';

// The small caps of a printed card form: "STIMMKARTE", "THEMA".
const FORM_LABEL =
  'text-[10px] font-bold uppercase leading-[14px] tracking-[0.14em] opacity-75';

type Props = {
  number: number;
  playDate: string;
  title: string;
  topic: string;
  /** Once played: the score stamped on the card. */
  score?: number;
  /** With the score: right or wrong per party, in seating order. */
  verdicts?: readonly { partyId: string; correct: boolean }[];
  /** Animate the stamp landing (the first time the result shows). */
  stamping?: boolean;
  /** The whole card becomes the button that casts it into the urn. */
  onCast?: () => void;
  /** Applied to the root, for the cast animation. */
  className?: string;
  ref?: Ref<HTMLElement>;
};

/**
 * The player's Stimmkarte. In a namentliche Abstimmung every MP drops a
 * personal card into the urn; the player gets one for their prediction. The
 * game's own logo stands where a real card prints "Deutscher Bundestag", and
 * the card never takes the blue, red or white of a real vote, so it can never
 * pass for an official one. Waiting to be cast on the result, it sits among
 * the feed cards there and takes their look; anywhere else it is an ink card
 * form whose title is the page's heading.
 */
function Stimmkarte(props: Props) {
  const { number, playDate, score, onCast, className, ref } = props;
  const scored = score !== undefined;
  const result = scored ? `, ${score} von ${MAX_SCORE} richtig` : '';
  const casting = onCast !== undefined && scored;

  const card = casting
    ? cn(
        CARD_SURFACE,
        'relative flex w-full flex-col gap-2.5 px-4 py-3.5 text-left text-[var(--daily-ink)]',
      )
    : 'relative flex w-full flex-col gap-3 rounded-[10px] bg-[var(--daily-ink)] p-4 pl-[18px] text-left text-[var(--daily-canvas)]';
  const inner: ReactNode = casting ? (
    <ScoredFace {...props} score={score} />
  ) : (
    <FormFace {...props} />
  );

  if (onCast) {
    return (
      <button
        ref={ref as Ref<HTMLButtonElement>}
        type="button"
        onClick={onCast}
        aria-label={`Stimmkarte vom ${voteDateShort(playDate)}${result}. In die Urne werfen`}
        className={cn(card, 'cursor-pointer', FOCUS_RING, className)}
      >
        {inner}
      </button>
    );
  }
  return (
    <div
      ref={ref as Ref<HTMLDivElement>}
      role="group"
      aria-label={`Stimmkarte, Tagesquiz Nummer ${number} vom ${formatDate(playDate)}${result}`}
      className={cn(card, className)}
    >
      {inner}
    </div>
  );
}

/**
 * A printed card form with the title as the page's heading, as a past day
 * opens on it. A played card carries the score stamped where the topic was.
 */
function FormFace({
  number,
  playDate,
  title,
  topic,
  score,
  stamping = false,
  onCast,
}: Props) {
  // A button cannot hold a heading.
  const Title = onCast ? 'span' : 'h1';
  return (
    <>
      <span
        aria-hidden
        className="pointer-events-none absolute inset-1.5 rounded-md border border-[var(--daily-muted)]"
      />
      <span className="relative flex items-center justify-between">
        <StimmtsLogo className="text-[17px]" />
        <span aria-hidden className={FORM_LABEL}>
          Stimmkarte
        </span>
      </span>
      <span className="relative flex items-stretch gap-4">
        <span className="flex min-w-0 flex-1 flex-col items-start gap-3">
          <Title className="hyphens-auto break-words text-2xl font-bold leading-[30px]">
            {title}
          </Title>
          {score !== undefined ? (
            // The stamp takes the topic's place, so it never covers the
            // title or the number.
            <span
              aria-hidden
              className={cn(
                'inline-block -rotate-6 whitespace-nowrap rounded-sm border-[2.5px] border-brand-red px-2 py-px font-display text-[19px] font-extrabold leading-6 tabular-nums text-brand-red',
                stamping && 'animate-stimmts-stamp motion-reduce:animate-none',
              )}
            >
              {score}/{MAX_SCORE} richtig
            </span>
          ) : (
            <span className="flex items-baseline gap-2 self-stretch">
              <span className={FORM_LABEL}>Thema</span>
              <span className="min-w-0 flex-1 truncate border-b border-dotted border-[var(--daily-muted)] pb-0.5 font-document text-[15px] italic leading-5">
                {topic}
              </span>
            </span>
          )}
        </span>
        <span
          aria-hidden
          className="flex flex-col items-center justify-center border-l border-[var(--daily-muted)] pl-4"
        >
          <span className="whitespace-nowrap text-xs font-medium opacity-75">
            Nr.
          </span>
          <span className="font-display text-[40px] font-extrabold tabular-nums leading-10">
            {number}
          </span>
          <span className="whitespace-nowrap text-xs font-medium opacity-75">
            {shortDay(playDate)}
          </span>
        </span>
      </span>
    </>
  );
}

/**
 * On the result, waiting to be cast: the feed card's layout, with the score
 * stamped beside the title. The stamp keeps its own column, so a long title wraps beside it
 * instead of running under it, down to the narrowest phone.
 */
function ScoredFace({
  playDate,
  title,
  topic,
  score,
  verdicts,
  stamping = false,
}: Props & { score: number }) {
  // The card's name is its aria-label; everything inside repeats it.
  return (
    <>
      <span
        aria-hidden
        className="flex items-center gap-1.5 text-[13px] text-[var(--daily-muted)]"
      >
        <StimmtsLogo className="text-[13px]" />
        <span>·</span>
        <span className="min-w-0 truncate">{feedDate(playDate)}</span>
      </span>
      <span aria-hidden className="flex items-start justify-between gap-3.5">
        <span className="min-w-0 flex-1 hyphens-auto break-words text-xl font-bold leading-[26px]">
          {title}
        </span>
        <span
          className={cn(
            'mr-1 mt-1 flex-none -rotate-6 whitespace-nowrap rounded-sm border-[2.5px] border-brand-red px-2 py-px font-display text-[17px] font-extrabold leading-[22px] tabular-nums text-brand-red',
            stamping && 'animate-stimmts-stamp motion-reduce:animate-none',
          )}
        >
          {score}/{MAX_SCORE} richtig
        </span>
      </span>
      {verdicts && (
        <span aria-hidden className="grid grid-cols-5 gap-1">
          {verdicts.map((entry) => (
            <span
              key={entry.partyId}
              className="flex flex-col items-center gap-1"
            >
              <PartyTile partyId={entry.partyId} size="sm" />
              <Verdict correct={entry.correct} className="size-5 text-[11px]" />
            </span>
          ))}
        </span>
      )}
      <span aria-hidden className="text-[13px] text-[var(--daily-muted)]">
        {topic}
      </span>
    </>
  );
}

export default Stimmkarte;
