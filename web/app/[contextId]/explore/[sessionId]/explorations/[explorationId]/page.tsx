import { ExplorationMain } from '@/modules/guided-exploration/components';

type Props = {
  params: Promise<{
    sessionId: string;
    explorationId: string;
  }>;
};

export default async function ExploreExplorationPage({ params }: Props) {
  const { sessionId, explorationId } = await params;

  return (
    <ExplorationMain
      initialSessionId={sessionId}
      initialExplorationId={explorationId}
    />
  );
}
