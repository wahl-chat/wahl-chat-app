'use client';

import { Volume2, Loader2, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTTSAudio } from '@/lib/hooks/use-tts-audio';

type Props = {
  partyId: string;
  messageId: string;
};

function ChatTtsButton({ partyId, messageId }: Props) {
  const { play, pause, status } = useTTSAudio(partyId, messageId);

  const isLoading = status === 'loading';
  const isPlaying = status === 'playing';

  const handleClick = () => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-8"
      onClick={handleClick}
      disabled={isLoading}
      title={isPlaying ? 'Wiedergabe stoppen' : 'Vorlesen'}
    >
      {isLoading && <Loader2 className="size-4 animate-spin" />}
      {isPlaying && <Square className="size-4" />}
      {!isLoading && !isPlaying && <Volume2 className="size-4" />}
    </Button>
  );
}

export default ChatTtsButton;
