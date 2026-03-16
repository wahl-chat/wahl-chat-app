'use client';

import {
  FreeRecallInput,
  type RecallData,
  getRouteForState,
  getStateFromResponse,
  studyApi,
} from '@/modules/exploration-study';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

export default function RecallPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const taskNumber = Number.parseInt(params.taskNumber as string) as 1 | 2;
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (data: RecallData) => {
    setIsSubmitting(true);
    const response = await studyApi.submitRecall(sessionId, taskNumber, data);
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
      <FreeRecallInput onSubmit={handleSubmit} isSubmitting={isSubmitting} />
    </div>
  );
}
