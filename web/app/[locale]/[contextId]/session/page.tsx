import ChatView from '@/components/chat/chat-view';
import { redirectLocalized } from '@/i18n/server-navigation';
import {
  getContext,
  getPartiesForContext,
} from '@/lib/firebase/firebase-server';
import { resolveLocale } from '@/lib/seo';
import { generateOgImageUrl } from '@/lib/utils';
import { getTranslations } from 'next-intl/server';

type Props = {
  params: Promise<{
    contextId: string;
  }>;
  searchParams: Promise<{
    session_id?: string;
    party_id: string[] | string | undefined;
    /** Sent as soon as the chat hydrates. */
    q?: string;
    /**
     * Put into the input for the user to send themselves. Entry points that a
     * crawler can reach — the landing page's example questions — use this, so
     * following the link never triggers a generation.
     */
    prefill?: string;
  }>;
};

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; contextId: string }>;
  searchParams: Promise<{
    party_id: string[];
    q?: string;
  }>;
}) {
  const { locale, contextId } = await params;
  const { party_id } = await searchParams;
  const t = await getTranslations({
    locale: resolveLocale(locale),
    namespace: 'chat.metadata',
  });

  const [context, parties] = await Promise.all([
    getContext(contextId),
    getPartiesForContext(contextId),
  ]);

  const contextName = context?.name ?? 'Chat';

  const partyId = Array.isArray(party_id)
    ? party_id.length === 1
      ? party_id[0]
      : undefined
    : party_id;

  const party = partyId
    ? parties.find((p) => p.party_id === partyId)
    : undefined;

  const title = party
    ? t('partyTitle', { party: party.name, election: contextName })
    : t('title', { election: contextName });

  const description = party
    ? t('partyDescription', { party: party.name, election: contextName })
    : t('description', { election: contextName });

  const ogImage = partyId ? await generateOgImageUrl(partyId) : undefined;

  return {
    title,
    description,
    robots: 'noindex',
    ...(ogImage && {
      openGraph: { images: [ogImage] },
    }),
  };
}

async function SessionPage({ params, searchParams }: Props) {
  const { contextId } = await params;
  const { party_id, q, prefill, session_id } = await searchParams;
  const parties = await getPartiesForContext(contextId);

  if (session_id) {
    return redirectLocalized(`/${contextId}/session/${session_id}`);
  }

  let normalizedPartyIds = Array.isArray(party_id)
    ? party_id
    : party_id
      ? [party_id]
      : undefined;

  normalizedPartyIds = normalizedPartyIds?.filter((id) =>
    parties.some((p) => p.party_id === id),
  );

  return (
    <ChatView
      partyIds={normalizedPartyIds}
      initialQuestion={q}
      prefilledQuestion={prefill}
      contextId={contextId}
    />
  );
}

export default SessionPage;
