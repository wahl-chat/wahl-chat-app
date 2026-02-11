import type { WahlSwiperStoreActionHandlerFor } from '@/lib/wahl-swiper/wahl-swiper-store.types';

export const swiperSetIsLoadingMessage: WahlSwiperStoreActionHandlerFor<
  'setIsLoadingMessage'
> = (get, set) => (isLoading) => {
  const currentThesis = get().getCurrentThesis();

  if (!currentThesis) {
    return;
  }

  set((state) => ({
    isLoadingMessage: {
      ...state.isLoadingMessage,
      [currentThesis.id]: isLoading,
    },
  }));
};
