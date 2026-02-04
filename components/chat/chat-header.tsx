import ChatContextSelector from '@/components/chat/chat-context-selector';
import HowToDialog from '@/components/how-to-dialog';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { SidebarTrigger } from '@/components/ui/sidebar';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { IS_EMBEDDED } from '@/lib/utils';
import { HelpCircleIcon } from 'lucide-react';
import ChatEmbedHeader from './chat-embed-header';
import ChatHeaderTitleDescription from './chat-header-title-description';
import ChatShareButton from './chat-share-button';
import CreateNewChatDropdownButton from './create-new-chat-dropdown-button';
import SocketDisconnectedBanner from './socket-disconnected-banner';

type Props = {
  contextId?: string;
};

async function ChatHeader({ contextId = DEFAULT_CONTEXT_ID }: Props) {
  if (IS_EMBEDDED) {
    return <ChatEmbedHeader />;
  }

  return (
    <>
      <header className="relative z-10 flex min-h-chat-header w-full flex-col">
        <div className="flex h-chat-header w-full gap-1 border-b border-b-muted bg-background px-4">
          <div className="flex min-w-0 items-center gap-2 overflow-x-hidden">
            <Tooltip>
              <TooltipTrigger asChild>
                <SidebarTrigger />
              </TooltipTrigger>
              <TooltipContent>Menü öffnen</TooltipContent>
            </Tooltip>
            <ChatHeaderTitleDescription />
          </div>
          <div className="hidden items-center gap-2 md:flex">
            <Separator orientation="vertical" />
            <ChatContextSelector />
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-1">
            <HowToDialog>
              <Button variant="ghost" size="icon" className="size-8">
                <HelpCircleIcon />
              </Button>
            </HowToDialog>
            <ChatShareButton contextId={contextId} />
            <CreateNewChatDropdownButton contextId={contextId} />
          </div>
        </div>
        <div className="flex h-chat-header w-full items-center border-b border-b-muted bg-background px-4 md:hidden">
          <ChatContextSelector />
        </div>
      </header>
      <SocketDisconnectedBanner />
    </>
  );
}

export default ChatHeader;
