import type { WahlSwiperStoreActionHandlerFor } from '@/lib/wahl-swiper/wahl-swiper-store.types';

export const swiperRemoveCard: WahlSwiperStoreActionHandlerFor<'removeCard'> =
  (get, set) => (swipe) => {
    set((state) => {
      state.history[state.thesesStack[state.thesesStack.length - 1].id] = swipe;
      state.thesesStack.pop();
    });
  };
