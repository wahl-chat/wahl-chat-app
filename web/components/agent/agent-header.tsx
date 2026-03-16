'use client';

import ConversationProgressIndicator from '@/components/agent/conversation-progress-indicator';
import { SidebarTrigger } from '@/components/ui/sidebar';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export default function AgentHeader() {
  return (
    <header className="relative z-10 flex h-[65px] w-full shrink-0 items-center gap-2 border-b border-b-muted bg-background px-4">
      {/* Sidebar trigger */}
      <Tooltip>
        <TooltipTrigger asChild>
          <SidebarTrigger />
        </TooltipTrigger>
        <TooltipContent>Menü öffnen</TooltipContent>
      </Tooltip>

      {/* Title */}
      <div className="hidden items-center gap-2 md:flex">
        <span className="text-lg font-semibold">Wahl Agent</span>
      </div>

      {/* Progress indicator */}
      <div className="absolute left-1/2 -translate-x-1/2">
        <ConversationProgressIndicator />
      </div>
    </header>
  );
}
