'use client';

import { BorderTrail } from '@/components/ui/border-trail';
import { Button } from '@/components/ui/button';
import type { StreamingMessage } from '@/lib/socket.types';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import { track } from '@vercel/analytics/react';
import { SquareCheckBig } from 'lucide-react';
import { useEffect, useState } from 'react';

type Props = {
  partyId: string;
  message: MessageItem | StreamingMessage;
  revealed?: boolean;
  onToggle?: () => void;
};

// Per-session flag (resets each browser session) so the circling green glow
// draws attention until the user opens PledgeTracker once, then calms down.
const PLEDGE_TRACKER_OPENED_KEY = 'wahlchat.pledgeTrackerOpened';

function ChatPledgeTrackerButton({
  partyId,
  message,
  revealed,
  onToggle,
}: Props) {
  const [showGlow, setShowGlow] = useState(false);

  useEffect(() => {
    try {
      setShowGlow(
        window.sessionStorage.getItem(PLEDGE_TRACKER_OPENED_KEY) !== 'true',
      );
    } catch {
      setShowGlow(false);
    }
  }, []);

  const handleClick = () => {
    track('pledge_tracker_button_clicked', {
      party: partyId,
      message: message.content ?? 'empty-message',
    });
    setShowGlow(false);
    try {
      window.sessionStorage.setItem(PLEDGE_TRACKER_OPENED_KEY, 'true');
    } catch {
      // Ignore storage failures; the toggle should still work.
    }
    onToggle?.();
  };

  return (
    <div className="relative rounded-md">
      <Button
        variant="outline"
        className="h-8 px-2 group-data-[has-message-background]:bg-zinc-100 group-data-[has-message-background]:hover:bg-zinc-200 group-data-[has-message-background]:dark:bg-zinc-900 group-data-[has-message-background]:dark:hover:bg-zinc-800"
        tooltip="Verwandte politische Ziele der Partei ansehen (PledgeTracker)"
        aria-haspopup="dialog"
        aria-expanded={revealed}
        onClick={handleClick}
      >
        <SquareCheckBig className="text-emerald-600 dark:text-emerald-400" />
        <span className="text-xs">PledgeTracker</span>
      </Button>
      {showGlow && (
        <>
          {/* Same BorderTrail config as ChatActionButtonHighlight — default
              size/speed and the big soft glow — with the traveling square kept
              faint + light so it reads as a moving glow, not a solid segment.
              The green bloom comes from the boxShadow, which is independent of
              the square's opacity. */}
          <BorderTrail
            className="bg-emerald-300/40"
            style={{
              boxShadow:
                '0px 0px 60px 30px rgb(110 231 183 / 55%), 0 0 100px 60px rgb(0 0 0 / 50%), 0 0 140px 90px rgb(0 0 0 / 50%)',
            }}
          />
          <span className="absolute right-[-2px] top-[-2px] flex size-[10px]">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75" />
            <span className="relative inline-flex size-[10px] rounded-full bg-red-500" />
          </span>
        </>
      )}
    </div>
  );
}

export default ChatPledgeTrackerButton;
