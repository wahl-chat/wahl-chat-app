'use client';

import { useLandingComposer } from '@/components/landing/landing-composer-provider';
import QuestionTopicIcon from '@/components/question-topic-icon';
import type { ProposedQuestion } from '@/lib/firebase/firebase.types';
import { ArrowUpRightIcon } from 'lucide-react';
import Link from 'next/link';

type Props = {
  contextId: string;
  questions: ProposedQuestion[];
};

function ExampleQuestions({ contextId, questions }: Props) {
  const { dispatch } = useLandingComposer();
  if (questions.length === 0) return null;

  return (
    <div className="mt-4 border-t border-border/70 pt-4 md:mt-0 md:border-0 md:pt-0">
      <p className="mb-2 px-3 text-xs text-muted-foreground">
        Ideen für deine erste Frage
      </p>
      <ul className="space-y-1">
        {questions.slice(0, 3).map((question) => (
          <li key={question.id}>
            {/* Prefill links preserve a review step before an answer is requested. */}
            <Link
              href={`/${contextId}/session?${new URLSearchParams({ prefill: question.content })}`}
              prefetch={false}
              onClick={(event) => {
                if (
                  event.button !== 0 ||
                  event.metaKey ||
                  event.ctrlKey ||
                  event.shiftKey ||
                  event.altKey
                )
                  return;
                event.preventDefault();
                dispatch({
                  type: 'suggestion',
                  contextId,
                  question: question.content,
                });
              }}
              className="group/question flex items-start justify-between gap-4 rounded-lg p-3 text-sm leading-relaxed text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <QuestionTopicIcon
                topic={question.topic}
                className="mt-1 size-4 shrink-0"
              />
              <span className="flex-1">{question.content}</span>
              <ArrowUpRightIcon
                className="mt-1 size-4 shrink-0 opacity-40 group-hover/question:opacity-100"
                aria-hidden="true"
              />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ExampleQuestions;
