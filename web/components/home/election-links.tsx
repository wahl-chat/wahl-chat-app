import { ContextIcon } from '@/components/context-icon';
import { Button } from '@/components/ui/button';
import type { Context } from '@/lib/firebase/firebase.types';
import { formatGermanDate } from '@/lib/utils';
import { ChevronDownIcon } from 'lucide-react';
import Link from 'next/link';

/**
 * Every election the site covers, as real links.
 *
 * Deliberately not a dropdown: / carries the site's inbound links, so it is
 * the page best placed to pass that authority on to each election page — and
 * a listbox of router pushes is not something a crawler can follow. Rendered
 * on the server for the same reason.
 *
 * Upcoming elections carry a border; concluded ones sit behind a collapsed
 * <details>, since nobody searches for an election that is over. It is a
 * native disclosure rather than a JS toggle on purpose: conditionally
 * rendered links never reach the server HTML, and being followable is the
 * whole point of listing them here.
 */

type Props = {
  upcoming: Context[];
  past: Context[];
  /** The election the panel already leads with; it needs no second link. */
  featuredId?: string;
};

function ElectionRow({
  contexts,
  concluded,
}: {
  contexts: Context[];
  concluded?: boolean;
}) {
  return (
    <ul className="flex flex-wrap items-center justify-center gap-2">
      {contexts.map((context) => {
        const date = formatGermanDate(context.date, 'medium');

        return (
          <li key={context.context_id}>
            <Button
              asChild
              variant={concluded ? 'ghost' : 'secondary'}
              size="sm"
              className={
                concluded
                  ? 'h-auto whitespace-normal px-2 py-1.5 text-xs font-normal text-muted-foreground'
                  : 'h-auto whitespace-normal border border-border px-3 py-1.5 text-xs'
              }
            >
              <Link
                href={`/${context.context_id}`}
                title={date ? `${context.name} – ${date}` : context.name}
              >
                <ContextIcon
                  context={context}
                  className="size-4 shrink-0 rounded-sm"
                />
                {context.name}
              </Link>
            </Button>
          </li>
        );
      })}
    </ul>
  );
}

function ElectionLinks({ upcoming, past, featuredId }: Props) {
  const otherUpcoming = upcoming.filter((c) => c.context_id !== featuredId);
  const otherPast = past.filter((c) => c.context_id !== featuredId);

  if (otherUpcoming.length === 0 && otherPast.length === 0) return null;

  return (
    <nav
      aria-label="Andere Wahlen"
      className="flex w-full max-w-4xl flex-col items-center gap-2"
    >
      {otherUpcoming.length > 0 && (
        <>
          <p className="text-sm text-muted-foreground">Andere Wahl auswählen</p>
          <ElectionRow contexts={otherUpcoming} />
        </>
      )}

      {otherPast.length > 0 && (
        <details className="group mt-1 w-full text-center">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-xs text-muted-foreground/70 transition-colors hover:text-muted-foreground [&::-webkit-details-marker]:hidden">
            Vergangene Wahlen auswählen
            <ChevronDownIcon
              className="size-3 transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
          </summary>

          <div className="pt-2">
            <ElectionRow contexts={otherPast} concluded />
          </div>
        </details>
      )}
    </nav>
  );
}

export default ElectionLinks;
