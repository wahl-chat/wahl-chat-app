import { WAHL_CHAT_PARTY_ID } from '@/lib/constants';
import type { ToolStatus } from '@/lib/stores/chat-store.types';
import { cn } from '@/lib/utils';
import { ChatMessageIcon } from './chat-message-icon';

/** What the general chat's agent is looking up, one line per tool call.
 * Shown until the answer's text streams. */
function ChatToolStatus({ lines }: { lines: ToolStatus[] }) {
  return (
    <div className="flex gap-3 md:gap-4">
      <ChatMessageIcon partyId={WAHL_CHAT_PARTY_ID} />
      <ul
        aria-live="polite"
        className="flex flex-col gap-1 pt-1.5 text-sm text-muted-foreground"
      >
        {lines.map((line) => (
          <li
            key={line.call_id}
            className={cn(line.state === 'running' && 'animate-pulse')}
          >
            {line.state === 'done' ? `✓ ${line.label}` : `${line.label} …`}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default ChatToolStatus;
