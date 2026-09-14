import { ContextIcon } from '@/components/context-icon';
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
 * Upcoming elections are cards; concluded ones sit behind a collapsed
 * <details>, since nobody searches for an election that is over. It is a
 * native disclosure rather than a JS toggle on purpose: conditionally
 * rendered links never reach the server HTML, and being followable is the
 * whole point of listing them here.
 *
 * The hero already leads with the featured election, so the caller passes the
 * others; between them the page still links every election, which is what the
 * ItemList structured data mirrors.
 */

type Props = {
  upcoming: Context[];
  past: Context[];
};

function ElectionCard({
  context,
  concluded,
}: {
  context: Context;
  concluded?: boolean;
}) {
  const date = formatGermanDate(context.date, 'medium');

  return (
    <li>
      <Link
        href={`/${context.context_id}`}
        className="group flex h-full items-center gap-3 rounded-md border border-border p-3 ring-offset-background transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
      >
        <ContextIcon context={context} className="size-8 shrink-0 rounded-sm" />

        <span className="flex min-w-0 flex-col">
          {/* Wraps rather than truncating: election names are long enough that
              an ellipsis hides which election a card is for. */}
          <span className="text-pretty font-medium group-hover:underline">
            {context.name}
          </span>

          {date && (
            <span className="text-xs text-muted-foreground">
              {concluded ? 'Wahl vom' : 'Wahl am'} {date}
            </span>
          )}
        </span>
      </Link>
    </li>
  );
}

function ElectionLinks({ upcoming, past }: Props) {
  if (upcoming.length === 0 && past.length === 0) return null;

  return (
    <nav aria-label="Alle Wahlen" className="flex flex-col gap-4">
      {upcoming.length > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {upcoming.map((context) => (
            <ElectionCard key={context.context_id} context={context} />
          ))}
        </ul>
      )}

      {past.length > 0 && (
        <details className="group">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
            Vergangene Wahlen anzeigen
            <ChevronDownIcon
              className="size-3 transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
          </summary>

          <ul className="grid gap-3 pt-3 sm:grid-cols-2 lg:grid-cols-3">
            {past.map((context) => (
              <ElectionCard
                key={context.context_id}
                context={context}
                concluded
              />
            ))}
          </ul>
        </details>
      )}
    </nav>
  );
}

export default ElectionLinks;
