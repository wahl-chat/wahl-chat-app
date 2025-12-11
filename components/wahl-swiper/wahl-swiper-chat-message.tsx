import { cn, prettifiedUrlName } from '@/lib/utils';
import type { SwiperMessage } from '@/lib/wahl-swiper/wahl-swiper-store.types';
import { ChatMessageIcon } from '@/components/chat/chat-message-icon';
import { Markdown } from '@/components/markdown';

type Props = {
  message: SwiperMessage;
};

function WahlSwiperChatMessage({ message }: Props) {
  const { role, content, sources } = message;

  const onReferenceClick = (number: number) => {
    if (number < 0 || number >= sources.length) {
      return;
    }

    const source = sources[number];
    window.open(source.source, '_blank');
  };

  const getReferenceTooltip = (number: number) => {
    if (number < 0 || number >= sources.length) {
      return null;
    }

    const source = sources[number];
    if (!source) {
      return null;
    }

    return source.source;
  };

  const getReferenceName = (number: number) => {
    if (number < 0 || number >= sources.length) {
      return null;
    }

    const source = sources[number];
    if (!source) {
      return null;
    }

    return prettifiedUrlName(source.source);
  };

  if (role === 'assistant') {
    return (
      <article
        className={cn(
          'flex w-fit max-w-[95%] rounded-[20px] text-foreground gap-3 md:gap-4',
          'self-start',
        )}
      >
        <ChatMessageIcon />
        <div className="flex flex-col">
          <Markdown
            getReferenceTooltip={getReferenceTooltip}
            getReferenceName={getReferenceName}
            onReferenceClick={onReferenceClick}
          >
            {content}
          </Markdown>
        </div>
      </article>
    );
  }

  return (
    <article className="flex w-fit max-w-[90%] self-end rounded-[20px] bg-muted px-4 py-2 text-foreground">
      <p>{content}</p>
    </article>
  );
}

export default WahlSwiperChatMessage;
