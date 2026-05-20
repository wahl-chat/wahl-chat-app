'use client';

import { cn } from '@/lib/utils';
import { useScreenTelemetry } from '@/modules/exploration-study/hooks/use-screen-telemetry';
import type {
  CognitiveLoadResponse,
  QuestionnaireData,
  UeqData,
} from '@/modules/exploration-study/types';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  CognitiveLoadForm,
  type CognitiveLoadFormSubmitData,
} from './cognitive-load-form';
import { UeqShortForm } from './ueq-short-form';

export interface QuestionnairePageProps {
  onSubmit: (data: QuestionnaireData) => Promise<void>;
  isSubmitting?: boolean;
  // When true, each questionnaire renders an optional qualitative free-text
  // field for the construct it measures.
  showQualitativeFeedback?: boolean;
  // Session id, used for behavioral integrity telemetry (item timing /
  // straightlining). Telemetry is skipped when absent.
  sessionId?: string;
  className?: string;
}

type Phase = 'cognitive-load' | 'ueq';

const PHASE_NUMBERS: Record<Phase, number> = {
  'cognitive-load': 1,
  ueq: 2,
};

const PHASE_LABELS: Record<Phase, string> = {
  'cognitive-load': 'Bewertung der Aufgabe',
  ueq: 'Benutzererfahrung',
};

export function QuestionnairePage({
  onSubmit,
  isSubmitting = false,
  showQualitativeFeedback = false,
  sessionId,
  className,
}: QuestionnairePageProps) {
  const [phase, setPhase] = useState<Phase>('cognitive-load');
  const [cognitiveLoadData, setCognitiveLoadData] =
    useState<CognitiveLoadResponse | null>(null);
  const [attentionCheckData, setAttentionCheckData] = useState<number | null>(
    null,
  );
  const headingRef = useRef<HTMLHeadingElement>(null);
  const isFirstRender = useRef(true);

  // Behavioral integrity telemetry. `item_timing` events carry the inter-item
  // interval (ms since the previous Likert change) so the admin can flag
  // straightlining. Field names are namespaced by phase.
  const { record } = useScreenTelemetry(sessionId ?? '', 'questionnaire', {
    enabled: Boolean(sessionId),
    trackCursorJumps: false,
  });
  const onCognitiveLoadItem = useCallback(
    (itemId: string, intervalMs: number) => {
      record({
        type: 'item_timing',
        itemId: `cl:${itemId}`,
        durationMs: intervalMs,
      });
    },
    [record],
  );
  const onUeqItem = useCallback(
    (itemId: string, intervalMs: number) => {
      record({
        type: 'item_timing',
        itemId: `ueq:${itemId}`,
        durationMs: intervalMs,
      });
    },
    [record],
  );

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    requestAnimationFrame(() => headingRef.current?.focus());
  }, [phase]);

  const handleCognitiveLoadSubmit = (data: CognitiveLoadFormSubmitData) => {
    setCognitiveLoadData(data.cognitiveLoad);
    setAttentionCheckData(data.attentionCheck);
    setPhase('ueq');
  };

  const handleUeqSubmit = async (ueqData: UeqData) => {
    if (!cognitiveLoadData || attentionCheckData === null) return;

    await onSubmit({
      cognitiveLoad: cognitiveLoadData,
      attentionCheck: attentionCheckData,
      ueqS: ueqData,
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
        {`Fragebogen Teil ${PHASE_NUMBERS[phase]} von 2: ${PHASE_LABELS[phase]}`}
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
          Teil {PHASE_NUMBERS[phase]} von 2: {PHASE_LABELS[phase]}
        </p>
      </div>

      {phase === 'cognitive-load' && (
        <CognitiveLoadForm
          onSubmit={handleCognitiveLoadSubmit}
          showQualitativeFeedback={showQualitativeFeedback}
          onItemAnswered={sessionId ? onCognitiveLoadItem : undefined}
        />
      )}

      {phase === 'ueq' && (
        <UeqShortForm
          onSubmit={handleUeqSubmit}
          isSubmitting={isSubmitting}
          showQualitativeFeedback={showQualitativeFeedback}
          onItemAnswered={sessionId ? onUeqItem : undefined}
        />
      )}
    </div>
  );
}
