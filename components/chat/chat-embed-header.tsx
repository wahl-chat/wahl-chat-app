import EmbedOpenWebsiteButton from '@/components/embed-open-website-button';
import HowToDialog from '@/components/how-to-dialog';
import { Button } from '@/components/ui/button';
import { SidebarTrigger } from '@/components/ui/sidebar';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { HelpCircleIcon } from 'lucide-react';
import SocketDisconnectedBanner from './socket-disconnected-banner';

function ChatEmbedHeader() {
  return (
    <>
      <header className="relative z-10 flex min-h-chat-header w-full items-center gap-1 border-b border-b-muted bg-background px-4">
        <div className="flex min-w-0 grow items-center gap-2 overflow-x-hidden">
          <Tooltip>
            <TooltipTrigger asChild>
              <SidebarTrigger />
            </TooltipTrigger>
            <TooltipContent>Menü öffnen</TooltipContent>
          </Tooltip>
        </div>
        <div className="flex items-center gap-1">
          <HowToDialog>
            <Button variant="ghost" size="icon" className="size-8">
              <HelpCircleIcon />
            </Button>
          </HowToDialog>
          <EmbedOpenWebsiteButton />
        </div>
      </header>

      <SocketDisconnectedBanner />
    </>
  );
}

export default ChatEmbedHeader;
