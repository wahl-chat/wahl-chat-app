import { ExplorationMain } from '@/modules/guided-exploration/components';

type Props = {
  params: Promise<{
    sessionId: string;
  }>;
};

export default async function ExploreSessionPage({ params }: Props) {
  const { sessionId } = await params;

  return <ExplorationMain initialSessionId={sessionId} />;
}
