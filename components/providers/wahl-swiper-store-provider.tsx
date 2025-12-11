'use client';
import {
  createWahlOMatStore,
  SWIPER_DEFAULT_QUICK_REPLIES,
} from '@/lib/wahl-swiper/wahl-swiper-store';
import type {
  SwiperMessage,
  Thesis,
  WahlSwiperStore,
} from '@/lib/wahl-swiper/wahl-swiper-store.types';
import { type ReactNode, createContext, useContext, useRef } from 'react';
import { useStore } from 'zustand';

export type WahlSwiperStoreApi = ReturnType<typeof createWahlOMatStore>;

export const WahlSwiperStoreContext = createContext<
  WahlSwiperStoreApi | undefined
>(undefined);

type Props = {
  children: ReactNode;
  allTheses: Thesis[];
};

export const WahlSwiperStoreProvider = ({ children, allTheses }: Props) => {
  const storeRef = useRef<WahlSwiperStoreApi>(null);

  if (!storeRef.current) {
    storeRef.current = createWahlOMatStore({
      allTheses,
      thesesStack: allTheses,
      messageHistory: allTheses.reduce(
        (acc, thesis) => {
          acc[thesis.id] = [];
          return acc;
        },
        {} as Record<string, SwiperMessage[]>,
      ),
      swiperInput: allTheses.reduce(
        (acc, thesis) => {
          acc[thesis.id] = '';
          return acc;
        },
        {} as Record<string, string>,
      ),
      isLoadingMessage: allTheses.reduce(
        (acc, thesis) => {
          acc[thesis.id] = false;
          return acc;
        },
        {} as Record<string, boolean>,
      ),
      currentQuickReplies: allTheses.reduce(
        (acc, thesis) => {
          acc[thesis.id] = SWIPER_DEFAULT_QUICK_REPLIES;
          return acc;
        },
        {} as Record<string, string[]>,
      ),
    });
  }

  return (
    <WahlSwiperStoreContext.Provider value={storeRef.current}>
      {children}
    </WahlSwiperStoreContext.Provider>
  );
};

export const useWahlSwiperStore = <T,>(
  selector: (store: WahlSwiperStore) => T,
): T => {
  const wahlOMatStoreContext = useContext(WahlSwiperStoreContext);

  if (!wahlOMatStoreContext) {
    throw new Error(
      `useWahlSwiperStore must be used within WahlSwiperStoreProvider`,
    );
  }

  return useStore(wahlOMatStoreContext, selector);
};
