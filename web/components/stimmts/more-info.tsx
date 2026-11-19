import { FOCUS_RING, META_TEXT } from '@/components/daily/card-styles';
import { formatDate, voteDateShort, weekdayName } from '@/lib/stimmts/labels';
import type { BillDocument, Puzzle } from '@/lib/stimmts/types';
import { cn } from '@/lib/utils';
import { ArrowLeft, ArrowUpRight, ChevronUp } from 'lucide-react';
import type { Ref } from 'react';

const BACK_BUTTON = cn(
  FOCUS_RING,
  'inline-flex min-h-11 items-center gap-1.5 self-start rounded-sm',
);

const DOC_LINK = cn(
  FOCUS_RING,
  'inline-flex min-h-10 items-center gap-1.5 rounded-full bg-[var(--daily-surface)] px-3.5 text-sm text-[var(--daily-ink)] transition-colors hover:bg-[var(--daily-border)]',
);

const DD = 'mt-0.5 text-[15px] leading-[22px] text-[var(--daily-body)]';

type Props = {
  id: string;
  puzzle: Puzzle;
  /** Hidden while the card shows its front; kept in the DOM for aria-controls. */
  hidden: boolean;
  headingRef: Ref<HTMLHeadingElement>;
  onClose: () => void;
};

/** "Gesetzentwurf der Bundesregierung, 21. Wahlperiode". */
function documentKind(document: BillDocument): string {
  const submitter =
    'initiator' in document
      ? document.initiator
      : `der Fraktion ${document.fraktion}`;
  const period = document.number.split('/')[0];
  return `${document.type} ${submitter}, ${period}. Wahlperiode`;
}

/**
 * The rest of the briefing: the full summary and the document the vote was
 * on. Below md it opens under the key points; from md up it is the back of
 * the card, so the way back sits on top there and at the end on a phone,
 * where the player has just scrolled through it.
 */
function MoreInfo({ id, puzzle, hidden, headingRef, onClose }: Props) {
  const { document } = puzzle;
  return (
    <div
      id={id}
      hidden={hidden}
      // A display class would beat the bare `hidden` attribute.
      className={cn(
        hidden ? 'hidden' : 'flex',
        'scroll-mt-[calc(var(--header-height)+16px)] flex-col gap-4 pb-2.5 pt-0.5 animate-in fade-in duration-200 md:pt-0',
      )}
    >
      <button
        type="button"
        onClick={onClose}
        className={cn(
          BACK_BUTTON,
          '-mb-1.5 -mt-2.5 hidden text-sm font-medium text-[var(--daily-muted)] md:inline-flex',
        )}
      >
        <ArrowLeft aria-hidden strokeWidth={2.25} className="size-4" />
        Zurück zu den Punkten
      </button>
      {/* Where focus lands on opening, so a screen reader starts here. */}
      <h3
        ref={headingRef}
        tabIndex={-1}
        className={cn(META_TEXT, 'font-normal outline-none')}
      >
        {document
          ? `Drucksache ${document.number} vom ${formatDate(document.date)}`
          : `Namentliche Abstimmung vom ${formatDate(puzzle.voteDate)}`}
      </h3>
      <p
        lang="de"
        className="hyphens-auto text-[15px] leading-[22px] text-[var(--daily-body)]"
      >
        {puzzle.briefing}
      </p>
      {document ? (
        <section className="flex flex-col gap-2.5 border-t border-[var(--daily-border)] pt-3.5">
          <h3 className="text-sm font-semibold text-[var(--daily-muted)]">
            Das Dokument
          </h3>
          <dl className="flex flex-col gap-2.5 [overflow-wrap:anywhere]">
            <div>
              <dt className={META_TEXT}>Art</dt>
              <dd className={DD}>{documentKind(document)}</dd>
            </div>
            <div>
              <dt className={META_TEXT}>Amtlicher Titel</dt>
              <dd lang="de" className={cn(DD, 'hyphens-auto')}>
                {document.title}
              </dd>
            </div>
            <div>
              <dt className={META_TEXT}>Abgestimmt</dt>
              <dd className={DD}>
                {weekdayName(puzzle.voteDate)}, {voteDateShort(puzzle.voteDate)}
                , namentlich
                {document.votedIn &&
                  `, in der Fassung der ${document.votedIn.label}`}
              </dd>
            </div>
          </dl>
          <div className="flex flex-wrap gap-2">
            <a
              href={document.url}
              target="_blank"
              rel="noopener noreferrer"
              className={DOC_LINK}
            >
              Drucksache {document.number} (PDF)
              <ArrowUpRight aria-hidden strokeWidth={2} className="size-3.5" />
            </a>
            {document.votedIn && (
              <a
                href={document.votedIn.url}
                target="_blank"
                rel="noopener noreferrer"
                className={DOC_LINK}
              >
                {document.votedIn.number} (PDF)
                <ArrowUpRight
                  aria-hidden
                  strokeWidth={2}
                  className="size-3.5"
                />
              </a>
            )}
          </div>
        </section>
      ) : (
        // Without a verified Drucksache, the vote's record is the source.
        <div className="flex flex-wrap gap-2 border-t border-[var(--daily-border)] pt-3.5">
          <a
            href={puzzle.source.url}
            target="_blank"
            rel="noopener noreferrer"
            className={DOC_LINK}
          >
            {puzzle.source.label}
            <ArrowUpRight aria-hidden strokeWidth={2} className="size-3.5" />
          </a>
        </div>
      )}
      <p className={META_TEXT}>Zusammenfassung von wahl.chat</p>
      <button
        type="button"
        onClick={onClose}
        className={cn(
          BACK_BUTTON,
          'text-[15px] font-semibold text-[var(--daily-ink)] md:hidden',
        )}
      >
        <ChevronUp aria-hidden strokeWidth={2.25} className="size-4" />
        Zurück zu den Punkten
      </button>
    </div>
  );
}

export default MoreInfo;
