'use client';

import {
  type DemographicsData,
  DemographicsForm,
  getRouteForState,
  getStateFromResponse,
  studyApi,
} from '@/modules/exploration-study';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

export default function DemographicsPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (data: DemographicsData) => {
    setIsSubmitting(true);
    const response = await studyApi.submitDemographics(sessionId, data);
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

  return (
    <div className="mx-auto w-full max-w-2xl">
      <DemographicsForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
    </div>
  );
}
