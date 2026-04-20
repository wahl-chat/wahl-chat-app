'use client';

import {
  ConsentForm,
  getRouteForState,
  getStateFromResponse,
  studyApi,
} from '@/modules/exploration-study';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

export default function ConsentPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (consentGiven: boolean) => {
    setIsSubmitting(true);
    setError(null);
    const response = await studyApi.submitConsent(sessionId, { consentGiven });
    if (response.error) {
      setError(response.error);
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
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-lg border border-destructive bg-destructive/10 p-4 text-destructive"
        >
          {error}
        </div>
      )}
      <ConsentForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
    </div>
  );
}
