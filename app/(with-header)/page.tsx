import ChatGroupPartySelect from '@/components/chat/chat-group-party-select';
import ContactCard from '@/components/home/contact-card';
import HomeInput from '@/components/home/home-input';
import HomePartyCards from '@/components/home/home-party-cards';
import HowToCard from '@/components/home/how-to-card';
import KnownFrom from '@/components/home/known-from';
import SupportUsCard from '@/components/home/support-us-card';
import SwiperTeaserCard from '@/components/home/swiper-teaser-card';
import { Button } from '@/components/ui/button';
import {
  getHomeInputProposedQuestions,
  getSystemStatus,
  getUser,
} from '@/lib/firebase/firebase-server';
import { IS_EMBEDDED } from '@/lib/utils';
import { GitCompareIcon, MousePointerClickIcon } from 'lucide-react';

export default async function Home() {
  const wahlChatQuestions = await getHomeInputProposedQuestions();
  const systemStatus = await getSystemStatus();
  const user = await getUser();

  return (
    <>
      {/* <KeepUpToDateTeaserCard initialUser={user} /> */}

      <div className="mt-4 flex w-full flex-row items-center justify-center gap-2">
        <MousePointerClickIcon />
        <h1 className="text-center text-sm font-semibold">
          Wähle eine Partei und stelle der KI deine Fragen
        </h1>
      </div>

      <HomePartyCards />

      <div className="w-full">
        <ChatGroupPartySelect>
          <Button
            className="mt-4 w-full max-w-xl whitespace-normal border border-border"
            variant="secondary"
          >
            <GitCompareIcon />
            Wähle mehrere Parteien zum Vergleichen
          </Button>
        </ChatGroupPartySelect>
      </div>

      <HomeInput
        className="hidden md:block"
        questions={wahlChatQuestions}
        initialSystemStatus={systemStatus}
        hasValidServerUser={!user?.isAnonymous}
      />

      {!IS_EMBEDDED && <KnownFrom />}

      {IS_EMBEDDED ? (
        <section className="mt-4">
          <HowToCard />
        </section>
      ) : (
        <section className="grid w-full grid-cols-1 flex-wrap gap-2 md:grid-cols-2 md:gap-2">
          <SwiperTeaserCard />
          {/* <TvTeaserCard /> */}
          <SupportUsCard />
          <HowToCard />
          <ContactCard />
        </section>
      )}

      <HomeInput
        className="md:hidden"
        questions={wahlChatQuestions}
        initialSystemStatus={systemStatus}
        hasValidServerUser={!user?.isAnonymous}
      />
    </>
  );
}
