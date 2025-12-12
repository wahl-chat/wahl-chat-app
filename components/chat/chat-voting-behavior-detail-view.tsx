'use client';

import { ChatVotingDetailsProvider } from '@/components/providers/chat-voting-details-provider';
import { Button } from '@/components/ui/button';
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '@/components/ui/carousel';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { Vote } from '@/lib/socket.types';
import { prettifiedUrlName } from '@/lib/utils';
import { ArrowUpRightIcon } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
import ChatVoteChartsHeader from './chat-vote-charts-header';
import ChatVoteDetailsHeader from './chat-vote-details-header';
import ChatVoteDetailsSlideCounter from './chat-vote-details-slide-counter';
import ChatVotingBehaviorDetailJustification from './chat-voting-behavior-detail-justification';
import ChatVotingBehaviorSubmittingParties from './chat-voting-behavior-submitting-parties';

type Props = {
  votes: Vote[];
  startIndex?: number;
  partyId: string;
};

function ChatVotingBehaviorDetailView({
  votes,
  startIndex = 0,
  partyId,
}: Props) {
  const [selectedPartyId, setSelectedPartyId] = useState(partyId);

  return (
    <ChatVotingDetailsProvider
      selectedPartyId={selectedPartyId}
      setSelectedPartyId={setSelectedPartyId}
    >
      <Carousel
        opts={{
          startIndex,
        }}
        className="flex h-full flex-col overflow-y-auto md:overflow-y-hidden"
      >
        <ChatVoteDetailsHeader votes={votes} />

        <section className="grow md:overflow-y-auto">
          <ChatVoteChartsHeader votes={votes} />

          <CarouselContent className="grow pb-16">
            {votes.map((vote) => (
              <CarouselItem key={vote.id}>
                <div className="p-4">
                  <div className="flex flex-row items-center justify-between">
                    <h2 className="text-base font-bold">Beschreibung</h2>
                    <Button variant="link" asChild>
                      <Link href={vote.url} target="_blank">
                        <ArrowUpRightIcon />
                        Zur Quelle
                      </Link>
                    </Button>
                  </div>

                  <p className="text-sm text-muted-foreground">
                    {vote.short_description}
                  </p>

                  <ChatVotingBehaviorDetailJustification vote={vote} />

                  <ChatVotingBehaviorSubmittingParties vote={vote} />

                  <p className="pb-2 pt-4 text-sm font-bold">Weitere Links</p>

                  <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
                    {vote.links.map((link, index) => (
                      <Tooltip key={link.url}>
                        <TooltipTrigger asChild>
                          <Link
                            key={link.url}
                            href={link.url}
                            target="_blank"
                            className="flex h-20 flex-col justify-between rounded-md border border-border p-2 transition-colors hover:border-primary hover:bg-muted"
                          >
                            <p className="line-clamp-2 text-sm">{link.title}</p>
                            <p className="text-xs text-muted-foreground">
                              {prettifiedUrlName(link.url)}
                            </p>
                          </Link>
                        </TooltipTrigger>
                        <TooltipContent
                          align={index === 0 ? 'start' : 'center'}
                        >
                          <p className="max-w-[300px] text-sm">{link.title}</p>
                        </TooltipContent>
                      </Tooltip>
                    ))}
                  </div>
                </div>
              </CarouselItem>
            ))}
          </CarouselContent>
        </section>
        <div className="fixed inset-x-0 bottom-0 flex flex-row items-center justify-center gap-4 border-t border-border bg-background/10 py-4 backdrop-blur-sm md:absolute">
          <CarouselPrevious />
          <ChatVoteDetailsSlideCounter votes={votes} />
          <CarouselNext />
        </div>
      </Carousel>
    </ChatVotingDetailsProvider>
  );
}

export default ChatVotingBehaviorDetailView;
