'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  CONVERSATION_STAGES,
  type ConversationStage,
} from '@/lib/stores/agent-store';
import { cn } from '@/lib/utils';
import { useTranslations } from 'next-intl';

// Stage ids are the backend's snake_case values; message keys are camelCase.
const STAGE_MESSAGE_KEYS = {
  start: 'start',
  active_listening: 'activeListening',
  party_positioning: 'partyPositioning',
  perspective_taking: 'perspectiveTaking',
  deliberation: 'deliberation',
  party_matching: 'partyMatching',
  end: 'end',
} as const satisfies Record<ConversationStage, string>;

const STATUS_MESSAGE_KEYS = {
  completed: 'statusCompleted',
  current: 'statusCurrent',
  upcoming: 'statusUpcoming',
} as const;

function getStageStatus(
  stage: ConversationStage,
  currentStage: ConversationStage | null,
): 'completed' | 'current' | 'upcoming' {
  if (!currentStage) return 'upcoming';
  const currentIndex = CONVERSATION_STAGES.indexOf(currentStage);
  const stageIndex = CONVERSATION_STAGES.indexOf(stage);
  if (stageIndex < currentIndex) return 'completed';
  if (stageIndex === currentIndex) return 'current';
  return 'upcoming';
}

export default function ConversationProgressIndicator() {
  const t = useTranslations('agent.progress');
  const conversationId = useAgentStore((state) => state.conversationId);
  const conversationStage = useAgentStore((state) => state.conversationStage);

  if (!conversationId) return null;

  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-xs text-muted-foreground">{t('label')}</span>
      <div className="flex items-center gap-1.5">
        {CONVERSATION_STAGES.map((stage) => {
          const status = getStageStatus(stage, conversationStage);
          const stageLabel = t(`stages.${STAGE_MESSAGE_KEYS[stage]}`);
          return (
            <Tooltip key={stage}>
              <TooltipTrigger asChild>
                <div
                  role="status"
                  aria-label={t('stageStatus', {
                    stage: stageLabel,
                    status: t(STATUS_MESSAGE_KEYS[status]),
                  })}
                  className={cn(
                    'h-2 w-4 rounded-full transition-all duration-300',
                    status === 'completed' && 'bg-primary',
                    status === 'current' &&
                      'bg-primary ring-2 ring-primary/30 ring-offset-1 ring-offset-background',
                    status === 'upcoming' && 'bg-muted',
                  )}
                />
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                {stageLabel}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}
