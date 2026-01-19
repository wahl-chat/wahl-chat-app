import WahlSwiperResult from '@/components/wahl-swiper/wahl-swiper-result';
import {
  getCurrentUser,
  getParties,
  getWahlSwiperHistory,
} from '@/lib/firebase/firebase-server';
import { getProlificCompletionCode } from '@/lib/study/prolific-server';
import { getUserDetailsFromUser } from '@/lib/utils';
import { wahlSwiperCalculateScore } from '@/lib/wahl-swiper/wahl-swiper-calculate-score';
import { notFound, redirect } from 'next/navigation';

type Props = {
  params: Promise<{
    resultId: string;
  }>;
};

async function WahlSwiperResultsPage({ params }: Props) {
  const { resultId } = await params;

  const user = await getCurrentUser();
  const history = await getWahlSwiperHistory(resultId).catch(() => {
    redirect('/swiper');
  });

  if (!history) {
    notFound();
  }

  const scores = await wahlSwiperCalculateScore(history.history);
  const parties = await getParties();
  const userDetails = user ? getUserDetailsFromUser(user) : undefined;

  // Get Prolific completion code if this is a study participant
  const prolificCompletionCode = history.is_prolific_study
    ? await getProlificCompletionCode()
    : null;

  return (
    <WahlSwiperResult
      resultId={resultId}
      scores={scores}
      parties={parties}
      userDetails={userDetails}
      prolificCompletionCode={prolificCompletionCode}
    />
  );
}

export default WahlSwiperResultsPage;
