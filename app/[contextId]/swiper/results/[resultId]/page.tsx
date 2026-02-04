import WahlSwiperResult from '@/components/wahl-swiper/wahl-swiper-result';
import {
  getCurrentUser,
  getPartiesForContext,
  getWahlSwiperHistory,
} from '@/lib/firebase/firebase-server';
import { getUserDetailsFromUser } from '@/lib/utils';
import { wahlSwiperCalculateScore } from '@/lib/wahl-swiper/wahl-swiper-calculate-score';
import { notFound, redirect } from 'next/navigation';

type Props = {
  params: Promise<{
    contextId: string;
    resultId: string;
  }>;
};

async function WahlSwiperResultsPage({ params }: Props) {
  const { contextId, resultId } = await params;

  const user = await getCurrentUser();
  const history = await getWahlSwiperHistory(resultId).catch(() => {
    redirect(`/${contextId}/swiper`);
  });

  if (!history) {
    notFound();
  }

  const scores = await wahlSwiperCalculateScore(history.history);
  const parties = await getPartiesForContext(contextId);
  const userDetails = user ? getUserDetailsFromUser(user) : undefined;

  return (
    <WahlSwiperResult
      resultId={resultId}
      scores={scores}
      parties={parties}
      userDetails={userDetails}
      contextId={contextId}
    />
  );
}

export default WahlSwiperResultsPage;
