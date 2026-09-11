import AiDisclaimer from '@/components/legal/ai-disclaimer';
import {
  getAccordionItem,
  parseLabeledListItem,
  splitOnSourceDomains,
} from '@/lib/how-to-content';
import Link from 'next/link';
import { Fragment } from 'react';

type Props = {
  /** The featured election's sources page. Never the bare /sources, which is
   *  a geo-IP redirect and would make this page depend on the requester. */
  sourcesHref: string;
};

/**
 * Where the answers come from.
 *
 * The copy is the how-to page's "Welche Daten werden verwendet?" answer, read
 * from the shared content module rather than restated. Its outro is skipped
 * on purpose: it names a bare /sources path, and this page links the featured
 * election's own sources page instead.
 */
function DataSources({ sourcesHref }: Props) {
  const item = getAccordionItem('data');
  if (!item) return null;

  const sources = item.content.orderedList ?? [];

  return (
    <div className="flex flex-col gap-6">
      <p className="text-muted-foreground">{item.content.intro}</p>

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {sources.map((source) => {
          const { label, text } = parseLabeledListItem(source);

          return (
            <li
              key={source}
              className="flex flex-col gap-2 rounded-md border border-border p-4"
            >
              <span className="font-bold text-foreground">{label}</span>
              <p className="text-sm text-muted-foreground">
                {splitOnSourceDomains(text).map((segment) =>
                  segment.href ? (
                    <a
                      key={segment.text}
                      href={segment.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline"
                    >
                      {segment.text}
                    </a>
                  ) : (
                    <Fragment key={segment.text}>{segment.text}</Fragment>
                  ),
                )}
              </p>
            </li>
          );
        })}
      </ul>

      <p className="text-sm text-muted-foreground">
        Welche Dokumente dahinterstehen, findest du auf der{' '}
        <Link href={sourcesHref} className="font-medium underline">
          Quellenseite
        </Link>
        .
      </p>

      <AiDisclaimer />
    </div>
  );
}

export default DataSources;
