import ChatView from '@/components/chat/chat-view';
import {
  getContext,
  getPartiesForContext,
} from '@/lib/firebase/firebase-server';
import { generateOgImageUrl } from '@/lib/utils';
import { redirect } from 'next/navigation';

type Props = {
  params: Promise<{
    contextId: string;
  }>;
  searchParams: Promise<{
    session_id?: string;
    party_id: string[] | string | undefined;
    q?: string;
  }>;
};

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ contextId: string }>;
  searchParams: Promise<{
    party_id: string[];
    q?: string;
  }>;
}) {
  const { contextId } = await params;
  const { party_id } = await searchParams;

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
    ? `Chat mit ${party.name} – ${contextName}`
    : `Chat – ${contextName}`;

  const description = party
    ? `Frage ${party.name} zu Positionen und Themen der ${contextName}. Quellengestützte Antworten bei wahl.chat.`
    : `Vergleiche Parteipositionen über die ${contextName} im Chat. Quellengestützte Antworten bei wahl.chat.`;

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
  const { party_id, q, session_id } = await searchParams;
  const parties = await getPartiesForContext(contextId);

  if (session_id) {
    redirect(`/${contextId}/session/${session_id}`);
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
      contextId={contextId}
    />
  );
}

export default SessionPage;
