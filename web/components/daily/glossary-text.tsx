'use client';

import {
  type GlossaryIndex,
  type TextPart,
  splitByRefs,
  splitLabel,
} from '@/lib/daily/glossary';
import type { GlossaryEntry, TermRef } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { createContext, useContext, useMemo } from 'react';
import { InfoTooltip } from './info-tooltip';

const GlossaryContext = createContext<GlossaryIndex>({});

/** The verified glossary for every term the feed below explains. Without
 * one, terms render as plain text. */
export function GlossaryProvider({
  entries,
  children,
}: {
  entries: GlossaryEntry[];
  children: React.ReactNode;
}) {
  const index = useMemo(
    () => Object.fromEntries(entries.map((e) => [e.term_id, e])),
    [entries],
  );
  return (
    <GlossaryContext.Provider value={index}>
      {children}
    </GlossaryContext.Provider>
  );
}

/** "bundestag.de" for a link to a page there. */
function sourceHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

const TERM_UNDERLINE =
  'underline decoration-dotted decoration-from-font underline-offset-[3px]';

/** A term with its explanation and the official page it rests on. */
function Term({
  text,
  entry,
  className = cn('inline rounded-sm text-left', TERM_UNDERLINE),
}: {
  text: string;
  entry: GlossaryEntry;
  className?: string;
}) {
  const [source] = entry.sources;
  return (
    <InfoTooltip
      label={`${text}: Erklärung anzeigen`}
      className={cn('cursor-help', className)}
      contentClassName="max-w-72"
      content={
        <>
          <p className="font-semibold">{entry.term}</p>
          <p className="mt-1">{entry.definition}</p>
          {source && (
            <p className="mt-1.5">
              Quelle:{' '}
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                title={source.title}
                className="underline underline-offset-2"
              >
                {sourceHost(source.url)}
              </a>
            </p>
          )}
        </>
      }
    >
      {text}
    </InfoTooltip>
  );
}

function Parts({ parts }: { parts: TextPart[] }) {
  return (
    <>
      {parts.map((part, i) =>
        part.entry ? (
          <Term key={`${i}-${part.text}`} text={part.text} entry={part.entry} />
        ) : (
          <span key={`${i}-${part.text}`}>{part.text}</span>
        ),
      )}
    </>
  );
}

/** An item's text with the terms the feed job found in it underlined. */
export function GlossaryText({
  text,
  terms,
}: {
  text: string;
  terms?: TermRef[];
}) {
  const glossary = useContext(GlossaryContext);
  if (!terms || terms.length === 0) {
    return <>{text}</>;
  }
  return <Parts parts={splitByRefs(text, terms, glossary)} />;
}

/** ``text`` explained by one known entry, in its own style (a badge): for
 * a label whose wording is not one of the term's forms ("nicht abg."). */
export function GlossaryTerm({
  text,
  termId,
  className,
}: {
  text: string;
  termId: string;
  className: string;
}) {
  const entry = useContext(GlossaryContext)[termId];
  if (!entry) {
    return <span className={className}>{text}</span>;
  }
  return (
    <Term text={text} entry={entry} className={cn(className, TERM_UNDERLINE)} />
  );
}

/** An office, a Gremium or a role in it, with the glossary terms it contains. */
export function GlossaryLabel({ label }: { label: string }) {
  const glossary = useContext(GlossaryContext);
  return <Parts parts={splitLabel(label, glossary)} />;
}
