import { TextLoop } from '@/components/ui/text-loop';

type Props = {
  messages: string[];
  interval?: number;
  fadeTime?: number;
  className?: string;
  onComplete?: () => void;
};

function AnimatedMessageSequence({ messages }: Props) {
  return (
    <TextLoop className="text-muted-foreground" interval={1.5}>
      {messages.map((message) => (
        <p key={message}>{message}</p>
      ))}
    </TextLoop>
  );
}

export default AnimatedMessageSequence;
