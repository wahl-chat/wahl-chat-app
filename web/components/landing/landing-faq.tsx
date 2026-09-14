import {
  WAHL_O_MAT_LIST_LEAD_IN,
  getLandingFaqItems,
  parseLabeledListItem,
} from '@/lib/how-to-content';
import type { HowToAccordionItem } from '@/lib/how-to-pdf-export';
import { ChevronDownIcon } from 'lucide-react';

/**
 * The five how-to answers a first-time visitor arrives with, as native
 * disclosures.
 *
 * Native <details> rather than the Radix accordion for the same reason
 * election-links.tsx gives: Radix does not mount closed content, so every
 * answer would be missing from the server HTML — and the answers being real
 * crawlable German text is the entire point of putting a FAQ on this page.
 * It also keeps the landing page free of a client-side accordion bundle.
 */
function FaqAnswer({ item }: { item: HowToAccordionItem }) {
  const { intro, orderedList, paragraphs } = item.content;

  return (
    <div className="flex flex-col gap-3 pb-4 text-sm text-muted-foreground">
      {intro && <p>{intro}</p>}

      {orderedList && orderedList.length > 0 && (
        <>
          {item.id === 'wahl-o-mat-difference' && (
            <p className="font-bold text-foreground">
              {WAHL_O_MAT_LIST_LEAD_IN}
            </p>
          )}

          <ol className="list-outside list-decimal pl-4 [&_li]:pt-1">
            {orderedList.map((entry) => {
              const { label, text } = parseLabeledListItem(entry);

              return (
                <li key={entry}>
                  {text ? (
                    <>
                      <span className="font-bold text-foreground">
                        {label}:
                      </span>{' '}
                      {text}
                    </>
                  ) : (
                    entry
                  )}
                </li>
              );
            })}
          </ol>
        </>
      )}

      {paragraphs?.map((paragraph) => (
        <p key={paragraph}>{paragraph}</p>
      ))}
    </div>
  );
}

function LandingFaq() {
  const items = getLandingFaqItems();

  if (items.length === 0) return null;

  return (
    <div className="flex flex-col">
      {items.map((item) => (
        <details key={item.id} className="group border-b border-border">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 [&::-webkit-details-marker]:hidden">
            <h3 className="text-left font-bold text-foreground">
              {item.title}
            </h3>
            <ChevronDownIcon
              className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
              aria-hidden="true"
            />
          </summary>

          <FaqAnswer item={item} />
        </details>
      ))}
    </div>
  );
}

export default LandingFaq;
