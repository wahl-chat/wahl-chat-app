'use client';

import {
  type QuestionnaireData,
  QuestionnairePage,
  getRouteForState,
  getStateFromResponse,
  studyApi,
  useStudySessionContext,
} from '@/modules/exploration-study';
import { Loader2 } from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

const QUALITATIVE_FEEDBACK_PATH = '/exploration-study/qualitative-feedback';

export default function QuestionnaireSurveyPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const session = useStudySessionContext();
  const isQualitative = session.studyType === 'qualitative';
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Qualitative runs have no questionnaire/quiz/demographics: once the task
  // ends the backend forwards everyone to this route, so for qualitative
  // sessions we send them straight on to the static qualitative-feedback page,
  // where the remainder of the session is moderated live. The target sits
  // outside the [sessionId] redirect guard, so this replace sticks.
  useEffect(() => {
    if (isQualitative) {
      router.replace(QUALITATIVE_FEEDBACK_PATH);
    }
  }, [isQualitative, router]);

  const handleSubmit = async (data: QuestionnaireData) => {
    setIsSubmitting(true);
    const response = await studyApi.submitQuestionnaire(sessionId, data);
    if (response.error) {
      setIsSubmitting(false);
      return;
    }
    const nextState = response.data
      ? getStateFromResponse(response.data)
      : undefined;
    if (nextState) {
      router.push(getRouteForState(sessionId, nextState));
      return;
    }
    // Success but no recognizable next state — re-enable the button rather
    // than leaving it stuck in the submitting state.
    setIsSubmitting(false);
  };

  // While the qualitative redirect above is in flight, show a loader rather
  // than flashing the questionnaire that these participants never fill out.
  if (isQualitative) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-[50vh] items-center justify-center"
      >
        <Loader2
          aria-hidden="true"
          className="size-8 animate-spin text-muted-foreground"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <QuestionnairePage
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
        showQualitativeFeedback={false}
        sessionId={sessionId}
      />
    </div>
  );
}
