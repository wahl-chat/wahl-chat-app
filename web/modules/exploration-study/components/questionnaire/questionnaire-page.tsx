'use client';

import { cn } from '@/lib/utils';
import type {
  CognitiveLoadResponse,
  ManipulationChecksData,
  QuestionnaireData,
  UeqData,
} from '@/modules/exploration-study/types';
import { useEffect, useRef, useState } from 'react';
import { CognitiveLoadForm } from './cognitive-load-form';
import { ManipulationChecksForm } from './manipulation-checks-form';
import { UeqShortForm } from './ueq-short-form';

export interface QuestionnairePageProps {
  onSubmit: (data: QuestionnaireData) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

type Phase = 'cognitive-load' | 'ueq' | 'manipulation-checks';

const PHASE_NUMBERS: Record<Phase, number> = {
  'cognitive-load': 1,
  ueq: 2,
  'manipulation-checks': 3,
};

const PHASE_LABELS: Record<Phase, string> = {
  'cognitive-load': 'Bewertung der Aufgabe',
  ueq: 'Benutzererfahrung',
  'manipulation-checks': 'Allgemeine Einschätzung',
};

export function QuestionnairePage({
  onSubmit,
  isSubmitting = false,
  className,
}: QuestionnairePageProps) {
  const [phase, setPhase] = useState<Phase>('cognitive-load');
  const [cognitiveLoadData, setCognitiveLoadData] =
    useState<CognitiveLoadResponse | null>(null);
  const [ueqData, setUeqData] = useState<UeqData | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const isFirstRender = useRef(true);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    requestAnimationFrame(() => headingRef.current?.focus());
  }, [phase]);

  const handleCognitiveLoadSubmit = (data: CognitiveLoadResponse) => {
    setCognitiveLoadData(data);
    setPhase('ueq');
  };

  const handleUeqSubmit = (data: UeqData) => {
    setUeqData(data);
    setPhase('manipulation-checks');
  };

  const handleManipulationChecksSubmit = async (
    manipulationChecks: ManipulationChecksData,
  ) => {
    if (!cognitiveLoadData || !ueqData) return;

    await onSubmit({
      cognitiveLoad: cognitiveLoadData,
      ueqS: ueqData,
      manipulationChecks,
    });
  };

  return (
    <div className={cn('mx-auto w-full max-w-2xl', className)}>
      <div
        role="status"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      >
        {`Fragebogen Teil ${PHASE_NUMBERS[phase]} von 3: ${PHASE_LABELS[phase]}`}
      </div>
      <div className="mb-6 space-y-2">
        <h1
          ref={headingRef}
          tabIndex={-1}
          className="text-2xl font-bold outline-none"
        >
          Fragebogen
        </h1>
        <p className="text-sm text-foreground">
          Teil {PHASE_NUMBERS[phase]} von 3: {PHASE_LABELS[phase]}
        </p>
      </div>

      {phase === 'cognitive-load' && (
        <CognitiveLoadForm onSubmit={handleCognitiveLoadSubmit} />
      )}

      {phase === 'ueq' && <UeqShortForm onSubmit={handleUeqSubmit} />}

      {phase === 'manipulation-checks' && (
        <ManipulationChecksForm
          onSubmit={handleManipulationChecksSubmit}
          isSubmitting={isSubmitting}
        />
      )}
    </div>
  );
}
