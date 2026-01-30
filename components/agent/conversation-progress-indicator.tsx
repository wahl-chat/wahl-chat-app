'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import {
  CONVERSATION_STAGES,
  STAGE_LABELS,
  type ConversationStage,
} from '@/lib/stores/agent-store';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

function getStageStatus(
  stage: ConversationStage,
  currentStage: ConversationStage | null
): 'completed' | 'current' | 'upcoming' {
  if (!currentStage) return 'upcoming';
  const currentIndex = CONVERSATION_STAGES.indexOf(currentStage);
  const stageIndex = CONVERSATION_STAGES.indexOf(stage);
  if (stageIndex < currentIndex) return 'completed';
  if (stageIndex === currentIndex) return 'current';
  return 'upcoming';
}

export default function ConversationProgressIndicator() {
  const conversationId = useAgentStore((state) => state.conversationId);
  const conversationStage = useAgentStore((state) => state.conversationStage);

  if (!conversationId) return null;

  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-xs text-muted-foreground">Fortschritt</span>
      <div className="flex items-center gap-1.5">
        {CONVERSATION_STAGES.map((stage) => {
          const status = getStageStatus(stage, conversationStage);
          const statusLabel =
            status === 'completed'
              ? 'abgeschlossen'
              : status === 'current'
                ? 'aktuell'
                : 'bevorstehend';
          return (
            <Tooltip key={stage}>
              <TooltipTrigger asChild>
                <div
                  role="status"
                  aria-label={`${STAGE_LABELS[stage]} - ${statusLabel}`}
                  className={cn(
                    'h-2 w-4 rounded-full transition-all duration-300',
                    status === 'completed' && 'bg-primary',
                    status === 'current' &&
                      'bg-primary ring-2 ring-primary/30 ring-offset-1 ring-offset-background',
                    status === 'upcoming' && 'bg-muted'
                  )}
                />
              </TooltipTrigger>
              <TooltipContent side="bottom" className="text-xs">
                {STAGE_LABELS[stage]}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}