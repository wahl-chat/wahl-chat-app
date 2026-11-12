'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import {
  type GlossaryIndex,
  type TextPart,
  splitByRefs,
  splitLabel,
} from '@/lib/daily/glossary';
import type { GlossaryEntry, TermRef } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { createContext, useContext, useMemo, useState } from 'react';
import { ABOVE_CARD_LINK, FOCUS_RING } from './card-styles';

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

/**
 * A term with its explanation: on hover with a mouse, on tap on a touch
 * screen, where a tooltip would otherwise never open. Inside a card it sits
 * above the card's link, so a tap explains rather than opens the item.
 */
function Term({ text, entry }: { text: string; entry: GlossaryEntry }) {
  const [open, setOpen] = useState(false);
  return (
    <Tooltip open={open} onOpenChange={setOpen} delayDuration={150}>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={`${text}: Erklärung anzeigen`}
          onClick={(event) => {
            // Inside a chip or a card the term must not trigger its parent.
            event.stopPropagation();
            setOpen(true);
          }}
          className={cn(
            ABOVE_CARD_LINK,
            FOCUS_RING,
            'inline cursor-help rounded-sm text-left underline decoration-dotted decoration-from-font underline-offset-[3px]',
          )}
        >
          {text}
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className={cn(
          DAILY_THEME_CLASSES,
          'max-w-72 border-[var(--daily-border)] bg-[var(--daily-canvas)] text-[13px] leading-snug text-[var(--daily-ink)]',
        )}
      >
        <p className="font-semibold">{entry.term}</p>
        <p className="mt-1">{entry.definition}</p>
      </TooltipContent>
    </Tooltip>
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

/** An office or Gremium role with the glossary terms it contains. */
export function GlossaryLabel({ label }: { label: string }) {
  const glossary = useContext(GlossaryContext);
  return <Parts parts={splitLabel(label, glossary)} />;
}
