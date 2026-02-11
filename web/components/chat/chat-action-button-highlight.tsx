import { BorderTrail } from '@/components/ui/border-trail';

type Props = {
  showHighlight?: boolean;
};

function ChatActionButtonHighlight({ showHighlight }: Props) {
  if (!showHighlight) return null;

  return (
    <>
      <BorderTrail
        style={{
          boxShadow:
            '0px 0px 60px 30px rgb(255 255 255 / 50%), 0 0 100px 60px rgb(0 0 0 / 50%), 0 0 140px 90px rgb(0 0 0 / 50%)',
        }}
      />
      <span className="absolute right-[-2px] top-[-2px] flex size-[10px]">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75" />
        <span className="relative inline-flex size-[10px] rounded-full bg-red-500" />
      </span>
    </>
  );
}

export default ChatActionButtonHighlight;
