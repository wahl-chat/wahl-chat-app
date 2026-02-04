import ContactCard from '@/components/home/contact-card';
import ElectionPartySelector from '@/components/home/election-party-selector';
import HomeInput from '@/components/home/home-input';
import HowToCard from '@/components/home/how-to-card';
import KnownFrom from '@/components/home/known-from';
import SupportUsCard from '@/components/home/support-us-card';
import {
  getHomeInputProposedQuestions,
  getSystemStatus,
  getUser,
} from '@/lib/firebase/firebase-server';
import { IS_EMBEDDED } from '@/lib/utils';

type Props = {
  params: Promise<{
    contextId: string;
  }>;
};

export default async function ContextHome({ params }: Props) {
  const { contextId } = await params;

  const [wahlChatQuestions, systemStatus, user] = await Promise.all([
    getHomeInputProposedQuestions(),
    getSystemStatus(),
    getUser(),
  ]);

  return (
    <>
      <div className="mt-4 w-full">
        <ElectionPartySelector contextId={contextId} />
      </div>

      <HomeInput
        className="hidden md:block"
        questions={wahlChatQuestions}
        initialSystemStatus={systemStatus}
        hasValidServerUser={!user?.isAnonymous}
        contextId={contextId}
      />

      {!IS_EMBEDDED && <KnownFrom />}

      {IS_EMBEDDED ? (
        <section className="mt-4">
          <HowToCard />
        </section>
      ) : (
        <section className="grid w-full grid-cols-1 flex-wrap gap-2 md:grid-cols-2 md:gap-2">
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
        contextId={contextId}
      />
    </>
  );
}
