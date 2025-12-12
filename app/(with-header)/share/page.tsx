import ShareChatInput from '@/components/share/share-chat-input';
import ShareGroupedMessage from '@/components/share/share-grouped-message';
import ShareScrollTop from '@/components/share/share-scroll-top';
import { Button } from '@/components/ui/button';
import { getSnapshot } from '@/lib/firebase/firebase-admin';
import {
  getCurrentUser,
  getParties,
  getSystemStatus,
} from '@/lib/firebase/firebase-server';
import { InternalReferrers } from '@/lib/internal-referrers';
import { cn, generateOgImageUrl } from '@/lib/utils';
import { ArrowLeftIcon } from 'lucide-react';
import Link from 'next/link';
import { redirect } from 'next/navigation';

type Props = {
  searchParams: Promise<{
    snapshot_id: string;
    ref?: InternalReferrers;
  }>;
};

export async function generateMetadata({ searchParams }: Props) {
  const { snapshot_id } = await searchParams;

  const snapshot = await getSnapshot(snapshot_id);

  if (snapshot.party_ids.length > 1) {
    return;
  }

  const partyId = snapshot.party_ids[0];

  return {
    openGraph: {
      images: [await generateOgImageUrl(partyId)],
    },
  };
}

async function SharePage({ searchParams }: Props) {
  const { snapshot_id, ref } = await searchParams;

  if (!snapshot_id) {
    redirect('/');
  }

  const snapshot = await getSnapshot(snapshot_id);
  const parties = await getParties();
  const isFromTopics = ref === InternalReferrers.TOPICS;
  const systemStatus = await getSystemStatus();
  const user = await getCurrentUser();

  return (
    <div className="relative flex h-full min-h-[calc(100vh-var(--header-height)-16px)] flex-col gap-4">
      <ShareScrollTop />
      {isFromTopics && (
        <Button variant="link" asChild className="mt-4 w-fit px-0">
          <Link href="/topics">
            <ArrowLeftIcon className="size-4" />
            Zurück zur Themenübersicht
          </Link>
        </Button>
      )}

      <div
        className={cn(
          'flex grow flex-col gap-6 overflow-y-auto',
          !isFromTopics && 'mt-4',
        )}
      >
        {snapshot.messages.map((message) => (
          <ShareGroupedMessage
            key={message.id}
            message={message}
            parties={parties.filter((p) =>
              snapshot.party_ids.includes(p.party_id),
            )}
          />
        ))}
      </div>
      <ShareChatInput
        snapshotId={snapshot_id}
        quickReplies={
          snapshot.messages.length > 1
            ? snapshot.messages[snapshot.messages.length - 1].quick_replies
            : []
        }
        initialSystemStatus={systemStatus}
        hasValidServerUser={!user?.isAnonymous}
      />
    </div>
  );
}

export default SharePage;
