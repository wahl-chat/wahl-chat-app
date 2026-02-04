import ChatView from '@/components/chat/chat-view';
import { getPartiesForContext } from '@/lib/firebase/firebase-server';
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
  searchParams,
}: {
  params: Promise<{ contextId: string }>;
  searchParams: Promise<{
    party_id: string[];
    q?: string;
  }>;
}) {
  const { party_id } = await searchParams;

  if (
    !party_id ||
    (Array.isArray(party_id) && (party_id.length === 0 || party_id.length > 1))
  ) {
    return;
  }

  const partyId = Array.isArray(party_id) ? party_id[0] : party_id;

  return {
    openGraph: {
      images: [await generateOgImageUrl(partyId)],
    },
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
