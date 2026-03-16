'use client';

import {
  type LiteracyData,
  LiteracyForm,
  getRouteForState,
  getStateFromResponse,
  studyApi,
} from '@/modules/exploration-study';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

export default function LiteracyPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (data: LiteracyData) => {
    setIsSubmitting(true);
    const response = await studyApi.submitLiteracy(sessionId, data);
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
      <LiteracyForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
    </div>
  );
}
