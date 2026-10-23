import {
  dottedDate,
  formatDate,
  submitterLine,
  timeAgo,
  weekdayName,
  yesMeaning,
} from '@/lib/stimmts/labels';
import type { BillDocument } from '@/lib/stimmts/types';
import CalendarLeaf from './calendar-leaf';
import { YesKey } from './yes-means';

const LINK =
  'underline underline-offset-2 focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';

// The printed sheet's body text: Times metrics, justified and hyphenated.
const SHEET_TEXT =
  'font-document text-[15px] leading-[21px] hyphens-auto text-justify';

type Props = {
  document: BillDocument;
  /** Our neutral summary, section A. */
  briefing: string;
  voteDate: string;
  /** The puzzle's day, from which "vor 4 Monaten" is counted. */
  playDate: string;
  yesMeans: string;
};

/** "21/6278": the Wahlperiode light, the number bold, as printed. */
function DrucksacheNumber({ number }: { number: string }) {
  const [period, own] = number.split('/');
  return (
    <span className="text-[15px] font-normal">
      {period}/<b className="font-bold">{own}</b>
    </span>
  );
}

/**
 * The vote presented as its bill: the Drucksache's cover page as the
 * Bundestag prints it, with only real metadata, then wahl.chat's neutral
 * summary in the sheet's own section style. Our sections carry our own
 * headings ("A. Worum es geht", never the bill's "A. Problem und Ziel"), the
 * footer says who wrote them, and the original PDF is one tap away.
 */
function BillSheet({
  document,
  briefing,
  voteDate,
  playDate,
  yesMeans,
}: Props) {
  return (
    <article
      lang="de"
      aria-label={`${document.type}, Drucksache ${document.number}`}
      className="relative mr-1"
    >
      {/* A second sheet peeks out underneath. */}
      <div className="relative flex flex-col rounded-[3px] border border-paper-rule bg-paper px-4 pb-4 pt-6 text-paper-ink shadow-[4px_4px_0_-1px_rgb(var(--paper)),4px_4px_0_0_rgb(var(--paper-rule))]">
        <header className="flex flex-col gap-0.5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-2">
            <span className="whitespace-nowrap text-[15px] font-bold leading-[22px]">
              Deutscher Bundestag
            </span>
            <span className="whitespace-nowrap text-xs font-bold leading-[22px]">
              Drucksache <DrucksacheNumber number={document.number} />
            </span>
          </div>
          <div className="flex flex-wrap items-baseline justify-between gap-x-2">
            <span className="text-xs font-bold leading-4">
              {document.number.split('/')[0]}. Wahlperiode
            </span>
            <span className="text-[10px] tabular-nums leading-4">
              {dottedDate(document.date)}
            </span>
          </div>
        </header>

        <h2 className="mt-8 text-[22px] font-bold leading-7">
          {document.type}
        </h2>
        <p className="mt-0.5 text-[13px] font-bold leading-[18px]">
          {submitterLine(document)}
        </p>
        <p className="mt-6 hyphens-auto break-words text-[15px] font-bold leading-5">
          {document.title}
        </p>

        <section className="mt-6 flex flex-col gap-2">
          <h3 className="text-[13px] font-bold leading-[18px]">
            A. Worum es geht
          </h3>
          <p className={SHEET_TEXT}>{briefing}</p>
        </section>

        <section className="mt-6 flex flex-col gap-2">
          <h3 className="text-[13px] font-bold leading-[18px]">
            B. Die Abstimmung
          </h3>
          <div className="flex items-center gap-3">
            <CalendarLeaf isoDate={voteDate} onPaper />
            <div className="flex min-w-0 flex-col gap-0.5 font-document text-[15px] leading-5">
              <p className="font-bold">Namentliche Abstimmung</p>
              <p className="text-paper-muted">
                {weekdayName(voteDate)}, {formatDate(voteDate)} ·{' '}
                {timeAgo(voteDate, playDate)}
              </p>
            </div>
          </div>
          {document.votedIn && (
            <p className={`${SHEET_TEXT} text-paper-muted`}>
              Abgestimmt in der Fassung der {document.votedIn.label},{' '}
              <a
                href={document.votedIn.url}
                target="_blank"
                rel="noopener noreferrer"
                className={LINK}
              >
                Drucksache {document.votedIn.number}
              </a>
              .
            </p>
          )}
          <p className="mt-1 flex items-start gap-2 font-document text-[15px] leading-[22px]">
            <YesKey className="bg-transparent shadow-[inset_0_0_0_1px_rgb(var(--paper-rule))]" />
            <span>bedeutet: {yesMeaning(yesMeans)}</span>
          </p>
        </section>

        <footer className="mt-6 flex flex-col gap-0.5 border-t border-paper-rule pt-2 text-[11px] leading-4 text-paper-muted">
          <span>A. und B.: neutrale Zusammenfassung von wahl.chat</span>
          <a
            href={document.url}
            target="_blank"
            rel="noopener noreferrer"
            className={`${LINK} text-paper-ink`}
          >
            Original: Drucksache {document.number} (PDF)
          </a>
        </footer>
      </div>
    </article>
  );
}

export default BillSheet;
