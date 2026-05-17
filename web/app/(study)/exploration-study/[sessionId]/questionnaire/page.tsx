'use client';

import {
  type QuestionnaireData,
  QuestionnairePage,
  getRouteForState,
  getStateFromResponse,
  studyApi,
  useStudySessionContext,
} from '@/modules/exploration-study';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

export default function QuestionnaireSurveyPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const session = useStudySessionContext();
  const showQualitativeFeedback = session.studyType === 'qualitative';
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (data: QuestionnaireData) => {
    setIsSubmitting(true);
    const response = await studyApi.submitQuestionnaire(sessionId, data);
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
      <QuestionnairePage
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
        showQualitativeFeedback={showQualitativeFeedback}
      />
    </div>
  );
}
