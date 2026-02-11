import { cx } from 'class-variance-authority';

import AnimatedMessageSequence from './animated-message-sequence';
import { ChatMessageIcon } from './chat-message-icon';

function ThinkingMessage() {
  const messages = [
    'Relevante Quellen ermitteln...',
    'Quellen analysieren...',
    'Daten verarbeiten...',
    'Ergebnisse generieren...',
    'Abschließen...',
  ];

  return (
    <div className={cx('flex gap-3 md:gap-4 items-center')}>
      <ChatMessageIcon />

      <AnimatedMessageSequence
        className="text-muted-foreground"
        messages={messages}
      />
    </div>
  );
}

export default ThinkingMessage;
