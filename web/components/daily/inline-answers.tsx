'use client';

import ChatMarkdown from '@/components/chat/chat-markdown';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import type { InlineAnswer } from '@/lib/daily/inline-answers';
import { cn } from '@/lib/utils';
import { FOCUS_RING, SECTION_LABEL } from './card-styles';

/** Precomputed answers to the item's suggested questions; a row opens in
 * place, the chat only for the follow-up. */
export function InlineAnswers({
  answers,
  onAsk,
}: {
  answers: InlineAnswer[];
  /** Absent while the feed's chat is off. */
  onAsk?: (question: string) => void;
}) {
  if (answers.length === 0) {
    return null;
  }
  return (
    <section className="flex flex-col gap-2 px-4 pt-6">
      <h3 className={SECTION_LABEL}>Mehr wissen?</h3>
      <Accordion type="single" collapsible className="flex flex-col gap-2">
        {answers.map((answer) => (
          <AccordionItem
            key={answer.question}
            value={answer.question}
            className="rounded-xl border border-[var(--daily-border)] bg-[var(--daily-surface)] px-4"
          >
            <AccordionTrigger
              className={cn(
                FOCUS_RING,
                'gap-3 py-3 text-[15px] font-semibold hover:no-underline',
              )}
            >
              {answer.question}
            </AccordionTrigger>
            <AccordionContent className="flex flex-col gap-2 text-[15px] leading-relaxed">
              <ChatMarkdown
                message={{ content: answer.text, sources: answer.sources }}
              />
              {onAsk && (
                <button
                  type="button"
                  onClick={() => onAsk(answer.question)}
                  className={cn(
                    FOCUS_RING,
                    'self-start rounded py-1 text-sm font-semibold hover:underline',
                  )}
                >
                  Im Chat weiterfragen →
                </button>
              )}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  );
}
