'use client';

import ChatGroupPartySelect from '@/components/chat/chat-group-party-select';
import { Accordion } from '@/components/ui/accordion';
import { Button } from '@/components/ui/button';
import type { PartyDetails } from '@/lib/party-details';
import { clearProlificMetadata } from '@/lib/study/prolific-params';
import type { UserDetails } from '@/lib/utils';
import type { PartiesScoreResult } from '@/lib/wahl-swiper/wahl-swiper.types';
import { RefreshCcwIcon } from 'lucide-react';
import Link from 'next/link';
import { useEffect } from 'react';
import WahlSwiperPartyResultCard from './wahl-swiper-party-result-card';
import WahlSwiperShareButton from './wahl-swiper-share-button';
import WahlSwiperSurveyLoginCard from './wahl-swiper-survey-login-card';

type Props = {
  resultId: string;
  scores: PartiesScoreResult;
  parties: PartyDetails[];
  userDetails?: UserDetails;
  isProlificStudy?: boolean;
  prolificCompletionCode?: string | null;
};

function WahlSwiperResult({
  resultId,
  scores,
  parties,
  userDetails,
  isProlificStudy,
  prolificCompletionCode,
}: Props) {
  const sortedScores = Object.entries(scores).sort(
    ([, score], [, otherScore]) => otherScore.score - score.score,
  );
  const hasValidScores = sortedScores.length > 0;

  // Clear Prolific metadata after study completion so user can restart with regular version
  useEffect(() => {
    if (isProlificStudy) {
      clearProlificMetadata();
    }
  }, [isProlificStudy]);

  return (
    <div className="relative mx-auto mt-4 flex w-full flex-col gap-4">
      {isProlificStudy && prolificCompletionCode && (
        <div className="rounded-lg border-2 border-green-500 bg-green-50 p-4 dark:bg-green-950">
          <h2 className="text-lg font-bold text-green-800 dark:text-green-200">
            Studie abgeschlossen!
          </h2>
          <p className="mt-1 text-sm text-green-700 dark:text-green-300">
            Vielen Dank für deine Teilnahme. Bitte kopiere den folgenden Code,
            um die Studie auf Prolific abzuschliessen:
          </p>
          <div className="mt-3 flex items-center gap-2">
            <code className="flex-1 rounded-md bg-white px-4 py-2 font-mono text-lg font-bold text-green-900 dark:bg-green-900 dark:text-green-100">
              {prolificCompletionCode}
            </code>
          </div>
        </div>
      )}
      {isProlificStudy && !prolificCompletionCode && (
        <div className="rounded-lg border-2 border-yellow-500 bg-yellow-50 p-4 dark:bg-yellow-950">
          <h2 className="text-lg font-bold text-yellow-800 dark:text-yellow-200">
            Studie abgeschlossen!
          </h2>
          <p className="mt-1 text-sm text-yellow-700 dark:text-yellow-300">
            Vielen Dank für deine Teilnahme. Der Abschlusscode ist leider nicht
            verfügbar. Bitte kontaktiere den Studienverantwortlichen.
          </p>
        </div>
      )}

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

      {hasValidScores ? (
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
      ) : (
        <div className="rounded-lg border border-muted bg-muted/50 p-6 text-center">
          <p className="text-muted-foreground">
            Keine Ergebnisse verfügbar. Um Übereinstimmungen mit den Parteien zu
            sehen, beantworte mindestens eine Frage mit Ja oder Nein.
          </p>
        </div>
      )}
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
