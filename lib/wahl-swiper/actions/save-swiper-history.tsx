import { saveWahlSwiperHistory } from '@/lib/firebase/firebase';
import type {
  SwiperMessage,
  WahlSwiperStoreActionHandlerFor,
} from '@/lib/wahl-swiper/wahl-swiper-store.types';

export const saveSwiperHistory: WahlSwiperStoreActionHandlerFor<
  'saveSwiperHistory'
> = (get) => (userId) => {
  const { history, messageHistory } = get();

  const normalizedMessageHistory = Object.entries(messageHistory).reduce(
    (acc, [thesisId, messages]) => {
      if (!messages.length) {
        return acc;
      }

      acc[thesisId] = messages.map((message) => ({
        ...message,
      }));

      return acc;
    },
    {} as Record<string, SwiperMessage[]>,
  );

  return saveWahlSwiperHistory(userId, history, normalizedMessageHistory);
};
