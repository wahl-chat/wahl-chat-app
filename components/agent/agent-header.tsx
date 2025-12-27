'use client';

import { SidebarTrigger } from '@/components/ui/sidebar';
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from '@/components/ui/tooltip';
import Logo from '@/components/chat/logo';

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

            {/* Logo and title */}
            <div className="flex items-center gap-2">
                <Logo variant="small" className="size-8" />
                <span className="text-lg font-semibold">Wahl Agent</span>
            </div>
        </header>
    );
}
