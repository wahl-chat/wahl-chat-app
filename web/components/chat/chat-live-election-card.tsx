'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import {
  useContexts,
  useCurrentContext,
} from '@/components/providers/context-provider';
import { nextLiveElections } from '@/lib/elections';
import { useChatSessionParam } from '@/lib/hooks/use-chat-session-param';
import { formatGermanDate } from '@/lib/utils';
import { ArrowRightIcon, VoteIcon } from 'lucide-react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';

/** Points a fresh general chat at elections that are about to happen. */
function ChatLiveElectionCard() {
  const isGeneral = useCurrentContext().type === 'general';
  const contexts = useContexts();
  // The store hydrates after first paint; these URLs already carry a chat.
  const searchParams = useSearchParams();
  const startsWithChat =
    useChatSessionParam() !== undefined ||
    searchParams.has('q') ||
    searchParams.has('feed_item') ||
    searchParams.has('poll_id');
  const isPristine = useChatStore(
    (state) =>
      state.input.trim() === '' &&
      state.messages.length === 0 &&
      state.currentStreamingMessages === undefined &&
      state.chatSessionId === undefined &&
      state.anchor === undefined,
  );

  if (!isGeneral || startsWithChat || !isPristine) return null;

  const elections = nextLiveElections(contexts);
  if (elections.length === 0) return null;

  return (
    <div className="mb-2 flex flex-col gap-2">
      {elections.map((election) => (
        <Link
          key={election.context_id}
          href={`/${election.context_id}/session`}
          className="group flex items-center gap-3 rounded-lg border bg-muted/50 px-3 py-2.5 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted group-hover:bg-background">
            <VoteIcon className="size-4" />
          </span>
          <span className="flex min-w-0 grow flex-col">
            <span className="line-clamp-2 text-sm font-semibold">
              {[election.name, formatGermanDate(election.date)]
                .filter(Boolean)
                .join(' · ')}
            </span>
            <span className="text-xs text-muted-foreground">
              Frag die Parteien zur Wahl
            </span>
          </span>
          <ArrowRightIcon className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
        </Link>
      ))}
    </div>
  );
}

export default ChatLiveElectionCard;
