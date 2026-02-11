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
    <header className="relative z-10 flex h-[65px] shrink-0 w-full items-center gap-2 border-b border-b-muted bg-background px-4">
      {/* Sidebar trigger */}
      <Tooltip>
        <TooltipTrigger asChild>
          <SidebarTrigger />
        </TooltipTrigger>
        <TooltipContent>Menü öffnen</TooltipContent>
      </Tooltip>

      {/* Title */}
      <div className="hidden md:flex items-center gap-2">
        <span className="text-lg font-semibold">Wahl Agent</span>
      </div>

      {/* Progress indicator */}
      <div className="absolute left-1/2 -translate-x-1/2">
        <ConversationProgressIndicator />
      </div>
    </header>
  );
}
