import WahlSwiperPartyResultCard from './wahl-swiper-party-result-card';
import { Button } from '@/components/ui/button';
import { Accordion } from '@/components/ui/accordion';
import type { PartiesScoreResult } from '@/lib/wahl-swiper/wahl-swiper.types';
import { RefreshCcwIcon } from 'lucide-react';
import type { PartyDetails } from '@/lib/party-details';
import WahlSwiperSurveyLoginCard from './wahl-swiper-survey-login-card';
import type { UserDetails } from '@/lib/utils';
import ChatGroupPartySelect from '@/components/chat/chat-group-party-select';
import WahlSwiperShareButton from './wahl-swiper-share-button';
import Link from 'next/link';

type Props = {
  resultId: string;
  scores: PartiesScoreResult;
  parties: PartyDetails[];
  userDetails?: UserDetails;
};

function WahlSwiperResult({ resultId, scores, parties, userDetails }: Props) {
  const sortedScores = Object.entries(scores).sort(
    ([, score], [, otherScore]) => otherScore.score - score.score,
  );

  return (
    <div className="relative mx-auto mt-4 flex w-full flex-col gap-4">
      <div className="flex flex-col">
        <h1 className="text-lg font-bold">Swiper Ergebnisse</h1>
        <p className="text-sm text-muted-foreground">
          Dieses Ergebnis dient nur zur ersten Orientierung. Hinterfrage es
          kritisch und sieh selbst in die Wahlprogramme - unser Vergleichs-Chat
          kann helfen:{' '}
          <ChatGroupPartySelect>
            <span className="underline">Vergleichs-Chat</span>
          </ChatGroupPartySelect>
        </p>
      </div>

      <WahlSwiperSurveyLoginCard
        resultId={resultId}
        userDetails={userDetails}
      />

      <Accordion type="single" collapsible className="flex flex-col gap-2">
        {sortedScores.map(([party, score]) => {
          const partyDetails = parties.find((p) => p.party_id === party);

          if (!partyDetails) {
            return null;
          }

          return (
            <WahlSwiperPartyResultCard
              key={party}
              party={partyDetails}
              score={score}
            />
          );
        })}
      </Accordion>
      <div className="sticky inset-x-0 bottom-0 z-10 bg-background/20 backdrop-blur-sm">
        <div className="mb-4 mt-2 grid grid-cols-2 gap-2">
          <Button asChild>
            <Link href="/swiper">
              <RefreshCcwIcon />
              Versuche es erneut
            </Link>
          </Button>
          <WahlSwiperShareButton />
        </div>
      </div>
    </div>
  );
}

export default WahlSwiperResult;
