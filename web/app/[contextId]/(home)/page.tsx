import ContactCard from '@/components/home/contact-card';
import ContextIntro from '@/components/home/context-intro';
import ElectionPartySelector from '@/components/home/election-party-selector';
import GitHubCard from '@/components/home/github-card';
import HomeInput from '@/components/home/home-input';
import HowToCard from '@/components/home/how-to-card';
import KnownFrom from '@/components/home/known-from';
import OpenCallCard, {
  getAvailableOpenCallUrl,
} from '@/components/home/open-call-card';
import SupportUsCard from '@/components/home/support-us-card';
import AiDisclaimer from '@/components/legal/ai-disclaimer';
import JsonLd from '@/components/seo/json-ld';
import {
  getContext,
  getHomeInputProposedQuestions,
  getPartiesForContext,
  getSystemStatus,
  getUser,
} from '@/lib/firebase/firebase-server';
import { buildContextCanonical, buildContextJsonLd } from '@/lib/seo';
import { IS_EMBEDDED } from '@/lib/utils';
import type { Metadata } from 'next';

type Props = {
  params: Promise<{
    contextId: string;
  }>;
};

// Only the canonical lives here — title, description, robots and Open Graph all
// come from app/[contextId]/layout.tsx. See buildContextCanonical for why the
// canonical must not be set at layout level.
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { contextId } = await params;
  return buildContextCanonical(contextId);
}

export default async function ContextHome({ params }: Props) {
  const { contextId } = await params;

  // getContext and getPartiesForContext are cached and already resolved by the
  // layout in this render, so these are reads from the same cache entry.
  const [wahlChatQuestions, systemStatus, user, openCallUrl, context, parties] =
    await Promise.all([
      getHomeInputProposedQuestions(),
      getSystemStatus(),
      getUser(),
      getAvailableOpenCallUrl(),
      getContext(contextId),
      getPartiesForContext(contextId),
    ]);

  return (
    <>
      {context && <JsonLd data={buildContextJsonLd(context)} />}

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
      <AiDisclaimer className="hidden md:block" />

      {!IS_EMBEDDED && <KnownFrom />}

      {IS_EMBEDDED ? (
        <section className="mt-4">
          <HowToCard />
        </section>
      ) : (
        <section className="grid w-full grid-cols-1 flex-wrap gap-2 md:grid-cols-2 md:gap-2">
          <SupportUsCard />
          <ContactCard />
          <GitHubCard fullWidth={!openCallUrl} />
          {openCallUrl && <OpenCallCard url={openCallUrl} />}
          <HowToCard />
        </section>
      )}

      <HomeInput
        className="md:hidden"
        questions={wahlChatQuestions}
        initialSystemStatus={systemStatus}
        hasValidServerUser={!user?.isAnonymous}
        contextId={contextId}
      />
      <AiDisclaimer className="md:hidden" />

      {context && !IS_EMBEDDED && (
        <ContextIntro context={context} parties={parties} />
      )}
    </>
  );
}
