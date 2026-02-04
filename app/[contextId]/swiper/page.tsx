import { WahlSwiperStoreProvider } from '@/components/providers/wahl-swiper-store-provider';
import WahlSwiper from '@/components/wahl-swiper/wahl-swiper';
import WahlSwiperChatWrapper from '@/components/wahl-swiper/wahl-swiper-chat-wrapper';
import WahlSwiperExperimentalDisclaimer from '@/components/wahl-swiper/wahl-swiper-experimental-disclaimer';
import {
  getContext,
  getWahlSwiperThesesForContext,
} from '@/lib/firebase/firebase-server';
import { redirect } from 'next/navigation';

type Props = {
  params: Promise<{
    contextId: string;
  }>;
};

async function SwiperPage({ params }: Props) {
  const { contextId } = await params;

  const context = await getContext(contextId);

  // Redirect if swiper is not supported for this context
  if (!context?.supports_swiper) {
    redirect(`/${contextId}`);
  }

  const thesesResponse = await getWahlSwiperThesesForContext(contextId);
  const theses = thesesResponse.map((thesis) => ({
    id: thesis.id,
    question: thesis.question,
    topic: thesis.topic,
  }));

  return (
    <WahlSwiperStoreProvider allTheses={theses} contextId={contextId}>
      <WahlSwiper />

      <WahlSwiperChatWrapper />

      <WahlSwiperExperimentalDisclaimer />
    </WahlSwiperStoreProvider>
  );
}

export default SwiperPage;
