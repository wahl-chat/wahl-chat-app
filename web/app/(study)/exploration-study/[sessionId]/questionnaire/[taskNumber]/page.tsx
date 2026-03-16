'use client';

import {
  type QuestionnaireData,
  QuestionnairePage,
  getRouteForState,
  getStateFromResponse,
  studyApi,
} from '@/modules/exploration-study';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

export default function QuestionnaireSurveyPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const taskNumber = Number.parseInt(params.taskNumber as string) as 1 | 2;
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (data: QuestionnaireData) => {
    setIsSubmitting(true);
    const response = await studyApi.submitQuestionnaire(
      sessionId,
      taskNumber,
      data,
    );
    if (response.error) {
      setIsSubmitting(false);
      return;
    }
    if (response.data) {
      const nextState = getStateFromResponse(response.data);
      if (nextState) {
        router.push(getRouteForState(sessionId, nextState));
      }
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl">
      <QuestionnairePage onSubmit={handleSubmit} isSubmitting={isSubmitting} />
    </div>
  );
}
