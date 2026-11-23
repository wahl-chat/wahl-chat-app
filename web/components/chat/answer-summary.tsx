'use client';

import { type SummaryPoint, pointAnchorId } from '@/lib/chat-summary';
import { ChevronRightIcon } from 'lucide-react';
import { useChatJump } from './chat-jump';

type Props = {
  id: string;
  points: SummaryPoint[];
  /** Labels that have a detail paragraph to jump to. */
  targets: ReadonlySet<string>;
};

/** An answer's "Kurz gesagt" block, in rows like the feed's vote table; a
 * point with details below jumps to them. */
function AnswerSummary({ id, points, targets }: Props) {
  const jumpState = useChatJump();
  return (
    <section
      id={id}
      tabIndex={-1}
      aria-label="Kurz gesagt"
      className="scroll-mt-4 rounded-xl border bg-muted/40 px-4 pb-1 pt-3 outline-none"
    >
      <p className="text-[13px] font-semibold text-muted-foreground">
        Kurz gesagt
      </p>
      <ul className="divide-y divide-border">
        {points.map((point, index) => {
          const text = (
            <span className="min-w-0 grow">
              <span className="font-semibold">{point.label}</span>
              {point.text && (
                <span className="text-muted-foreground"> {point.text}</span>
              )}
            </span>
          );
          const target = pointAnchorId(id, point.label);
          return (
            <li key={`${index}-${point.label}`}>
              {jumpState && targets.has(point.label) ? (
                <button
                  type="button"
                  onClick={() => jumpState.jump(id, target)}
                  className="flex min-h-11 w-full items-center gap-3 py-2 text-left transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {text}
                  <ChevronRightIcon
                    className="size-4 shrink-0 text-muted-foreground"
                    aria-hidden
                  />
                </button>
              ) : (
                <p className="flex py-2">{text}</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default AnswerSummary;
