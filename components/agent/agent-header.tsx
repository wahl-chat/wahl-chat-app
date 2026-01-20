'use client';

import ConversationProgressIndicator from '@/components/agent/conversation-progress-indicator';
import Logo from '@/components/chat/logo';
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

      {/* Logo and title */}
      <div className="flex items-center gap-2">
        <Logo variant="small" className="size-8" />
        <span className="text-lg font-semibold">Wahl Agent</span>
      </div>

      {/* Progress indicator */}
      <div className="ml-auto pr-8">
        <ConversationProgressIndicator />
      </div>
    </header>
  );
}
