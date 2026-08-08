'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { CheckCircle2 } from 'lucide-react';

type Props = {
  minInteractions: number;
};

function ChatProlificProgress({ minInteractions }: Props) {
  const prolificMessageCount = useChatStore(
    (state) => state.prolificMessageCount,
  );

  const isComplete = prolificMessageCount >= minInteractions;
  const progressValue = Math.min(
    (prolificMessageCount / Math.max(minInteractions, 1)) * 100,
    100,
  );

  return (
    <div
      className={cn(
        'mb-3 rounded-lg border p-3',
        isComplete
          ? 'border-green-500 bg-green-50 dark:bg-green-950'
          : 'border-muted bg-muted/50',
      )}
    >
      <div className="flex items-center justify-between text-sm">
        <span
          className={cn(
            'font-medium',
            isComplete
              ? 'text-green-800 dark:text-green-200'
              : 'text-muted-foreground',
          )}
        >
          {isComplete ? (
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="size-4" />
              Studienanforderung erfüllt!
            </span>
          ) : (
            `${prolificMessageCount} von ${minInteractions} Nachrichten`
          )}
        </span>
      </div>
      {!isComplete && <Progress value={progressValue} className="mt-2 h-2" />}
    </div>
  );
}

export default ChatProlificProgress;
