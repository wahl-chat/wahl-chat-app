import Logo from '@/components/chat/logo';
import { formatDate, shortDay } from '@/lib/stimmts/labels';
import { cn } from '@/lib/utils';
import type { Ref } from 'react';

// The small caps of a printed card form: "STIMMKARTE", "THEMA".
const FORM_LABEL =
  'text-[10px] font-bold uppercase leading-[14px] tracking-[0.14em] opacity-75';

type Props = {
  number: number;
  playDate: string;
  title: string;
  topic: string;
  /** On the result: the score stamped where the topic was. */
  score?: number;
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
 * wahl.chat wordmark stands where a real card prints "Deutscher Bundestag",
 * and the card is ink, never the blue, red or white of a real vote, so it can
 * never pass for an official one.
 */
function Stimmkarte({
  number,
  playDate,
  title,
  topic,
  score,
  stamping = false,
  onCast,
  className,
  ref,
}: Props) {
  const scored = score !== undefined;
  const label = `Stimmkarte, Tagesrätsel Nummer ${number} vom ${formatDate(playDate)}${
    scored ? `, ${score} von 5 richtig` : ''
  }`;
  // On the briefing the title is the page's heading; on the result the card
  // is a button, which cannot hold one.
  const Title = onCast ? 'span' : 'h1';

  const inner = (
    <>
      <span
        aria-hidden
        className="pointer-events-none absolute inset-1.5 rounded-md border border-muted-foreground"
      />
      <span className="relative flex items-center justify-between">
        <Logo variant="large" className="w-[84px] text-current" />
        <span aria-hidden className={FORM_LABEL}>
          Stimmkarte
        </span>
      </span>
      <span className="relative flex items-stretch gap-4">
        <span className="flex min-w-0 flex-1 flex-col items-start gap-3">
          <Title className="hyphens-auto break-words text-2xl font-bold leading-[30px]">
            {title}
          </Title>
          {scored ? (
            // The stamp takes the topic's place, so it never covers the
            // title or the number.
            <span
              aria-hidden
              className={cn(
                'inline-block -rotate-6 whitespace-nowrap rounded-sm border-[2.5px] border-brand-red px-2 py-px font-display text-[19px] font-extrabold leading-6 tabular-nums text-brand-red',
                stamping && 'animate-stimmts-stamp motion-reduce:animate-none',
              )}
            >
              {score}/5 richtig
            </span>
          ) : (
            <span className="flex items-baseline gap-2 self-stretch">
              <span className={FORM_LABEL}>Thema</span>
              <span className="min-w-0 flex-1 truncate border-b border-dotted border-muted-foreground pb-0.5 font-document text-[15px] italic leading-5">
                {topic}
              </span>
            </span>
          )}
        </span>
        <span
          aria-hidden
          className="flex flex-col items-center justify-center border-l border-muted-foreground pl-4"
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

  const card =
    'relative flex w-full flex-col gap-3 rounded-[10px] bg-foreground p-4 pl-[18px] text-left text-background';

  if (onCast) {
    return (
      <button
        ref={ref as Ref<HTMLButtonElement>}
        type="button"
        onClick={onCast}
        aria-label={`${label}. In die Urne werfen`}
        className={cn(
          card,
          'cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          className,
        )}
      >
        {inner}
      </button>
    );
  }
  return (
    <div
      ref={ref as Ref<HTMLDivElement>}
      role="group"
      aria-label={label}
      className={cn(card, className)}
    >
      {inner}
    </div>
  );
}

export default Stimmkarte;
