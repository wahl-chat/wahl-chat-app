import Logo from '@/components/chat/logo';
import MessageLoadingBorderTrail from '@/components/chat/message-loading-border-trail';
import { useWahlSwiperStore } from '@/components/providers/wahl-swiper-store-provider';
import { Button } from '@/components/ui/button';
import { useIsDesktop } from '@/lib/hooks/use-is-desktop';
import { cn } from '@/lib/utils';
import { SWIPER_DEFAULT_QUICK_REPLIES } from '@/lib/wahl-swiper/wahl-swiper-store';
import {
  ArrowUp,
  ChevronDown,
  MessageCircleMoreIcon,
  XIcon,
} from 'lucide-react';

type Props = {
  isSticky: boolean;
  handleToggleExpand: () => void;
  handleNewMessage?: (message: string) => void;
};

function WahlSwiperInput({
  isSticky,
  handleToggleExpand,
  handleNewMessage,
}: Props) {
  const setInput = useWahlSwiperStore((state) => state.setSwiperInput);
  const input = useWahlSwiperStore((state) => {
    const currentThesis = state.getCurrentThesis();
    if (!currentThesis) return '';

    return state.swiperInput[currentThesis.id];
  });
  const addUserMessage = useWahlSwiperStore((state) => state.addUserMessage);
  const isLoadingMessage = useWahlSwiperStore((state) => {
    const currentThesis = state.getCurrentThesis();
    if (!currentThesis) return false;
    return state.isLoadingMessage[currentThesis.id];
  });
  const showExpandToggle = useWahlSwiperStore((state) => {
    const currentThesis = state.getCurrentThesis();
    if (!currentThesis) return false;

    return state.messageHistory[currentThesis.id]?.length > 0;
  });
  const chatIsExpanded = useWahlSwiperStore((state) => state.chatIsExpanded);
  const isDesktop = useIsDesktop();
  const currentQuickReplies = useWahlSwiperStore((state) => {
    const currentThesis = state.getCurrentThesis();
    if (!currentThesis) return SWIPER_DEFAULT_QUICK_REPLIES;

    return state.currentQuickReplies[currentThesis.id];
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    addUserMessage(input);
    handleNewMessage?.(input);
    setInput('');
  };

  const handleQuickReplyClick = (reply: string) => {
    addUserMessage(reply);
    setInput('');
    handleNewMessage?.(reply);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={cn(
        'relative shadow-2xl transition-shadow duration-300 max-w-xl mx-auto w-full grid overflow-hidden rounded-[20px] border border-input dark:focus-within:border-zinc-700 focus-within:border-zinc-300 bg-chat-input ease-out md:shadow-none min-h-[82px]',
        !isSticky && 'shadow-none',
      )}
    >
      {isLoadingMessage && <MessageLoadingBorderTrail />}

      <div className="flex gap-1 overflow-x-auto whitespace-nowrap px-2 pt-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {showExpandToggle && (
          <button
            className={cn(
              'shrink-0 rounded-full bg-primary py-1 px-2 text-primary-foreground flex items-center gap-1',
            )}
            type="button"
            onClick={handleToggleExpand}
          >
            {!isDesktop ? (
              <ChevronDown
                className={cn('size-3 transition-transform', {
                  'rotate-180': !chatIsExpanded,
                })}
              />
            ) : chatIsExpanded ? (
              <XIcon className="size-3" />
            ) : (
              <MessageCircleMoreIcon className="size-3" />
            )}
            <span className="text-xs">
              Chat {chatIsExpanded ? 'schließen' : 'öffnen'}
            </span>
          </button>
        )}
        {currentQuickReplies?.map((reply) => {
          return (
            <button
              key={reply}
              className={cn(
                'shrink-0 rounded-full bg-muted px-2 py-1 transition-colors enabled:hover:bg-muted/70 disabled:cursor-not-allowed disabled:opacity-50',
              )}
              type="button"
              disabled={isLoadingMessage}
              onClick={() => handleQuickReplyClick(reply)}
            >
              <p className="line-clamp-1 text-xs">{reply}</p>
            </button>
          );
        })}
      </div>

      <Logo
        variant="small"
        className="absolute bottom-2 left-2 size-8 translate-y-0 rounded-full border border-border p-1"
      />
      <input
        className="w-full bg-chat-input px-12 py-3 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed"
        name="question"
        placeholder="Frage wahl.chat..."
        value={input}
        type="text"
        onChange={(e) => setInput(e.target.value)}
        maxLength={500}
      />
      <Button
        type="submit"
        className={cn(
          'absolute right-2 bottom-2 translate-y-0 flex size-8 items-center justify-center rounded-full bg-foreground text-background transition-colors hover:bg-foreground/80 disabled:bg-foreground/20 disabled:text-muted',
        )}
        disabled={!input.length || isLoadingMessage}
      >
        <ArrowUp className="size-4 font-bold" />
      </Button>
    </form>
  );
}

export default WahlSwiperInput;
