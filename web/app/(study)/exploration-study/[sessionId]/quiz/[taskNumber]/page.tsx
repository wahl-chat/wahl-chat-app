'use client';

import {
  type QuizAnswer,
  QuizDisplay,
  getRouteForState,
  getStateFromResponse,
  studyApi,
} from '@/modules/exploration-study';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

export default function QuizPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const taskNumber = Number.parseInt(params.taskNumber as string) as 1 | 2;
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (answers: QuizAnswer[]) => {
    setIsSubmitting(true);
    const response = await studyApi.submitQuiz(sessionId, taskNumber, answers);
    if (response.error) {
      setIsSubmitting(false);
      return;
    }
    if (response.data) {
      const nextState = getStateFromResponse(response.data);
      if (nextState) {
        router.push(getRouteForState(sessionId, nextState));
      } else {
        setIsSubmitting(false);
      }
    } else {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl">
      <QuizDisplay
        sessionId={sessionId}
        taskNumber={taskNumber}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
      />
    </div>
  );
}
