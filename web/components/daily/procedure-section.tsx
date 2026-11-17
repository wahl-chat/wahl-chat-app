'use client';

import {
  type ProcedureMarker,
  type ProcedureRow,
  type TimelineStep,
  passedVote,
  procedureChatHref,
  procedureMarker,
  procedureSection,
  votedOnAmendment,
} from '@/lib/daily/procedures';
import type { ProcedureSummary } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import {
  ArrowUpRightIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  MessageCircleIcon,
  SparklesIcon,
} from 'lucide-react';
import Link from 'next/link';
import { useId, useState } from 'react';
import { FOCUS_RING, MUTED_TEXT, PILL, SECTION_LABEL } from './card-styles';
import { SourceLink } from './vote-panels';

const shortDay = new Intl.DateTimeFormat('de-DE', {
  day: '2-digit',
  month: '2-digit',
  year: '2-digit',
  timeZone: 'UTC',
});

function dayLabel(iso: string | null): string {
  return iso ? shortDay.format(new Date(`${iso}T00:00:00Z`)) : 'offen';
}

const NOTE: Partial<Record<TimelineStep['state'], string>> = {
  latest: 'Aktueller Stand',
  next: 'Als Nächstes',
};

// One size for every dot; the item's own step is a little larger and in the
// accent colour, the step still to come only outlined.
function Dot({ state }: { state: TimelineStep['state'] }) {
  return (
    <span
      aria-hidden
      className={cn(
        'relative z-10 block shrink-0 rounded-full',
        state === 'here'
          ? 'size-[18px] bg-[var(--daily-accent)] ring-4 ring-[var(--daily-accent-soft)]'
          : state === 'next'
            ? 'size-3.5 border-2 border-dashed border-[var(--daily-muted)] bg-[var(--daily-canvas)]'
            : 'size-3.5 bg-[var(--daily-ink)]',
      )}
    />
  );
}

function StepPanel({
  step,
  vorgangId,
  id,
}: {
  step: TimelineStep;
  vorgangId: string;
  id: string;
}) {
  return (
    <div
      id={id}
      className="mb-2 mt-1 flex flex-col gap-2.5 rounded-xl bg-[var(--daily-surface)] p-3 text-[14px] leading-relaxed text-[var(--daily-body)]"
    >
      {step.facts && <p>{step.facts}</p>}
      {step.summary && (
        <div className="flex flex-col gap-1">
          <span
            className={cn(
              'inline-flex items-center gap-1 text-xs font-semibold',
              MUTED_TEXT,
            )}
          >
            <SparklesIcon className="size-3.5" aria-hidden />
            KI-Zusammenfassung der Drucksache
          </span>
          <p className="text-[var(--daily-ink)]">{step.summary}</p>
        </div>
      )}
      {step.links.length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {step.links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                FOCUS_RING,
                'inline-flex items-center gap-1 rounded-sm text-[13px] underline underline-offset-4',
                MUTED_TEXT,
              )}
            >
              {link.label}
              <ArrowUpRightIcon className="size-3.5" aria-hidden />
            </a>
          ))}
        </div>
      )}
      {step.question && (
        <Link
          href={procedureChatHref(vorgangId, step.question)}
          className={cn(
            FOCUS_RING,
            'inline-flex min-h-9 items-center gap-1.5 self-start rounded-full border border-[var(--daily-border)] px-3 text-[13px] font-semibold text-[var(--daily-ink)] transition-colors hover:bg-[var(--daily-canvas)]',
          )}
        >
          <MessageCircleIcon className="size-3.5" aria-hidden />
          Mehr dazu im Chat
        </Link>
      )}
    </div>
  );
}

function Timeline({
  steps,
  here,
  procedure,
}: {
  steps: TimelineStep[];
  here: string;
  procedure: ProcedureSummary;
}) {
  const vorgangId = procedure.vorgang_id;
  const [open, setOpen] = useState<number | null>(null);
  const baseId = useId();
  return (
    <ol className="flex flex-col">
      {steps.map((step, i) => {
        const note =
          step.state === 'here'
            ? here
            : step.state === 'latest' && passedVote(step, procedure)
              ? 'Beschlossen'
              : NOTE[step.state];
        const isOpen = open === i;
        const panelId = `${baseId}-${i}`;
        const toNext = steps[i + 1]?.state === 'next';
        return (
          <li key={`${step.date ?? 'next'}-${step.label}`} className="relative">
            {/* The line to the next step: solid through the past, dashed
                into what is still to come. */}
            {i < steps.length - 1 && (
              <span
                aria-hidden
                className={cn(
                  // From this dot's centre to the next one's, under both.
                  'absolute -bottom-[18px] left-[9px] top-[18px] border-l-2 border-[var(--daily-muted)]',
                  toNext && 'border-dashed',
                )}
              />
            )}
            <button
              type="button"
              aria-expanded={isOpen}
              aria-controls={panelId}
              onClick={() => setOpen(isOpen ? null : i)}
              className={cn(
                FOCUS_RING,
                'grid w-full grid-cols-[20px_64px_minmax(0,1fr)_16px] items-start gap-x-2 rounded-md py-1.5 text-left',
              )}
            >
              <span className="flex h-6 items-center justify-center">
                <Dot state={step.state} />
              </span>
              <span
                className={cn('text-[13px] tabular-nums leading-6', MUTED_TEXT)}
              >
                {dayLabel(step.date)}
              </span>
              <span className="flex flex-col">
                <span
                  className={cn(
                    'text-[15px] leading-6',
                    step.state === 'here' &&
                      'font-bold text-[var(--daily-accent)]',
                    step.state === 'latest' && 'font-semibold',
                    step.state === 'next' && MUTED_TEXT,
                  )}
                >
                  {step.label}
                </span>
                {note && (
                  <span
                    className={cn(
                      'text-xs',
                      step.state === 'here'
                        ? 'font-semibold text-[var(--daily-accent)]'
                        : MUTED_TEXT,
                    )}
                  >
                    {note}
                  </span>
                )}
              </span>
              <ChevronDownIcon
                aria-hidden
                className={cn(
                  'mt-1 size-4 transition-transform',
                  MUTED_TEXT,
                  isOpen && 'rotate-180',
                )}
              />
            </button>
            {isOpen && (
              <div className="pl-[30px]">
                <StepPanel step={step} vorgangId={vorgangId} id={panelId} />
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function RowLink({ row }: { row: ProcedureRow }) {
  return (
    <Link
      href={procedureChatHref(row.procedure.vorgang_id, 'Wie ging es weiter?')}
      className={cn(
        FOCUS_RING,
        'grid grid-cols-[minmax(0,1fr)_16px] items-center gap-x-2 rounded-md py-3',
      )}
    >
      <span className="flex flex-col gap-1.5">
        <span className="flex flex-wrap items-center gap-1.5 text-xs font-semibold">
          {row.authors.length > 0 && (
            <span className="rounded-md bg-[var(--daily-surface)] px-2 py-0.5">
              {row.authors.join(' · ')}
            </span>
          )}
          {row.status && (
            <span
              className={cn(
                'rounded-md px-2 py-0.5',
                row.status === 'Angenommen'
                  ? 'bg-[var(--daily-yes-bg)] text-[var(--daily-yes)]'
                  : row.status === 'Abgelehnt'
                    ? 'bg-[var(--daily-no-bg)] text-[var(--daily-no)]'
                    : 'bg-[var(--daily-surface)]',
              )}
            >
              {row.status}
            </span>
          )}
        </span>
        <span className="text-[15px] leading-snug">{row.procedure.titel}</span>
      </span>
      <ChevronRightIcon className={cn('size-4', MUTED_TEXT)} />
    </Link>
  );
}

function Rows({ rows }: { rows: ProcedureRow[] }) {
  return (
    <ul className="flex flex-col divide-y divide-[var(--daily-border)]">
      {rows.map((row) => (
        <li key={row.procedure.vorgang_id}>
          <RowLink row={row} />
        </li>
      ))}
    </ul>
  );
}

function moreLabel(more: ProcedureRow[]): string {
  const resolutions = more.every((r) =>
    r.procedure.titel.startsWith('Entschließungsantrag'),
  );
  if (resolutions) {
    return more.length === 1
      ? '+ 1 Entschließungsantrag'
      : `+ ${more.length} Entschließungsanträge`;
  }
  return more.length === 1
    ? '+ 1 weiteres Verfahren'
    : `+ ${more.length} weitere Verfahren`;
}

const DIP_LABEL = 'Verfahren im Dokumentationssystem des Bundestags (DIP)';

/** Where the item's law stands, with this item's step highlighted, each
 * step opening what happened there, and the ways into the chat about it
 * (flows F-11/F-12). Nothing without procedures. */
export function ProcedureSection({
  day,
  kind,
  procedures,
  voteTitle,
}: {
  day: string;
  kind: 'vote' | 'debate';
  procedures: ProcedureSummary[] | undefined;
  /** The vote's own title: tells an amendment from the law. */
  voteTitle?: string;
}) {
  const section = procedureSection(day, procedures);
  if (!section) {
    return null;
  }
  if (section.type === 'list') {
    return (
      <section className="flex flex-col gap-1 px-4 pt-6">
        <h3 className={SECTION_LABEL}>
          {section.rows.length === 1
            ? 'Debattiert: 1 Antrag'
            : `Debattiert: ${section.rows.length} Anträge`}
        </h3>
        <Rows rows={section.rows} />
      </section>
    );
  }
  const { main, steps, questions, more } = section;
  return (
    <section className="flex flex-col gap-3 px-4 pt-6">
      <div className="flex flex-col gap-0.5">
        <p className={SECTION_LABEL}>So ging es im Bundestag voran</p>
        <h3 className="text-[15px] font-semibold leading-snug">{main.titel}</h3>
        {section.status && (
          <p className="text-[14px] font-semibold text-[var(--daily-accent)]">
            {section.status}
          </p>
        )}
        <p className={cn('text-[13px]', MUTED_TEXT)}>
          Wähle einen Schritt, um zu sehen, was dort passiert ist.
        </p>
      </div>
      <Timeline
        steps={steps}
        here={
          kind === 'debate'
            ? 'Diese Debatte'
            : votedOnAmendment(voteTitle)
              ? 'Diese Abstimmung: über einen Änderungsantrag'
              : 'Diese Abstimmung'
        }
        procedure={main}
      />
      {questions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {questions.map((question) => (
            <Link
              key={question}
              href={procedureChatHref(main.vorgang_id, question)}
              className={cn(
                FOCUS_RING,
                PILL,
                'whitespace-normal font-semibold',
              )}
            >
              <MessageCircleIcon className="size-4 shrink-0" aria-hidden />
              {question}
            </Link>
          ))}
        </div>
      )}
      {more.length > 0 && (
        <details className="group border-t border-[var(--daily-border)] pt-2">
          <summary
            className={cn(
              FOCUS_RING,
              'flex min-h-10 cursor-pointer items-center rounded-md text-[15px]',
            )}
          >
            {moreLabel(more)}
          </summary>
          <Rows rows={more} />
        </details>
      )}
      {main.dip_url.startsWith('https://') && (
        <SourceLink href={main.dip_url}>{DIP_LABEL}</SourceLink>
      )}
    </section>
  );
}

/** On a feed card: the law's type, its course as dots and the step the item
 * belongs to, so a reader sees there is a timeline behind it. */
export function ProcedureMarkerLine({ marker }: { marker: ProcedureMarker }) {
  return (
    <p
      className={cn(
        'flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[13px]',
        MUTED_TEXT,
      )}
    >
      {/* Plain text: the line is a hint, the card itself opens the detail. */}
      <span className="text-xs font-semibold uppercase tracking-wide">
        {marker.tag}
      </span>
      <span className="flex items-center gap-2.5 whitespace-nowrap">
        <span aria-hidden className="flex items-center">
          {marker.states.map((state, i) => (
            <span key={`${i}-${state}`} className="flex items-center">
              {i > 0 && (
                <span
                  className={cn(
                    'block w-3 border-t-2',
                    state === 'next'
                      ? 'border-dashed border-[var(--daily-muted)]'
                      : 'border-[var(--daily-muted)]',
                  )}
                />
              )}
              <span
                className={cn(
                  'block rounded-full',
                  state === 'here'
                    ? 'size-[11px] bg-[var(--daily-accent)] ring-[3px] ring-[var(--daily-accent-soft)]'
                    : state === 'next'
                      ? 'size-2.5 border-[1.5px] border-dashed border-[var(--daily-muted)]'
                      : 'size-2.5 bg-[var(--daily-ink)]',
                )}
              />
            </span>
          ))}
        </span>
        <span aria-hidden className="font-semibold text-[var(--daily-ink)]">
          {marker.step}
        </span>
      </span>
      <span className="sr-only">
        {`Schritt ${marker.states.findIndex((s) => s === 'here') + 1 || marker.states.filter((s) => s !== 'next').length} von ${marker.states.length}: ${marker.step}`}
      </span>
    </p>
  );
}

export function CardProcedureMarker({
  day,
  procedures,
  voteTitle,
}: {
  day: string;
  procedures: ProcedureSummary[] | undefined;
  voteTitle?: string;
}) {
  const marker = procedureMarker(day, procedures, voteTitle);
  return marker ? <ProcedureMarkerLine marker={marker} /> : null;
}
