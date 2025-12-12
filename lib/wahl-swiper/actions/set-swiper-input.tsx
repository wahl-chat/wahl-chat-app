import type { WahlSwiperStoreActionHandlerFor } from '@/lib/wahl-swiper/wahl-swiper-store.types';

export const setSwiperInput: WahlSwiperStoreActionHandlerFor<'setSwiperInput'> =
  (get, set) => (input) => {
    const currentThesis = get().getCurrentThesis();

    if (!currentThesis) {
      return;
    }

    set((state) => ({
      swiperInput: {
        ...state.swiperInput,
        [currentThesis.id]: input,
      },
    }));
  };
