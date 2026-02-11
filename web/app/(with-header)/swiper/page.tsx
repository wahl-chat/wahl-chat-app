import { WahlSwiperStoreProvider } from '@/components/providers/wahl-swiper-store-provider';

import WahlSwiper from '@/components/wahl-swiper/wahl-swiper';
import WahlSwiperChatWrapper from '@/components/wahl-swiper/wahl-swiper-chat-wrapper';
import { getWahlSwiperTheses } from '@/lib/firebase/firebase-server';
import WahlSwiperDisclaimerWrapper from "@/components/wahl-swiper/wahl-swiper-disclaimer-wrapper";

async function WahlOMatPage() {
  const thesesResponse = await getWahlSwiperTheses();
  const theses = thesesResponse.map((thesis) => ({
    id: thesis.id,
    question: thesis.question,
    topic: thesis.topic,
  }));

  return (
    <WahlSwiperStoreProvider allTheses={theses}>
      <WahlSwiper />

      <WahlSwiperChatWrapper />

      <WahlSwiperDisclaimerWrapper />
    </WahlSwiperStoreProvider>
  );
}

export default WahlOMatPage;
