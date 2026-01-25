'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import LoadingSpinner from '@/components/loading-spinner';
import { useWahlSwiperStore } from '@/components/providers/wahl-swiper-store-provider';
import { useRouter } from 'next/navigation';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import SwipingCards from './swiping-cards';

function WahlSwiper() {
  const [isLoading, setIsLoading] = useState(false);
  const finished = useWahlSwiperStore(
    (state) => state.thesesStack.length === 0,
  );
  const saveSwiperHistory = useWahlSwiperStore(
    (state) => state.saveSwiperHistory,
  );
  const { user } = useAnonymousAuth();
  const router = useRouter();

  const handleFinished = useCallback(async () => {
    const errorToast = () =>
      toast.error(
        'Fehler beim Berechnen deiner Ergebnisse. Bitte lade die Seite neu.',
      );

    if (!user) {
      errorToast();
      return;
    }

    setIsLoading(true);

    try {
      const resultId = await saveSwiperHistory(user.uid);
      router.push(`/swiper/results/${resultId}`);
    } catch (error) {
      console.error(error);
      errorToast();
      setIsLoading(false);
    }
  }, [user, router, saveSwiperHistory]);

  useEffect(() => {
    if (finished) {
      handleFinished();
    }
  }, [finished, handleFinished]);

  const swipingCards = useMemo(() => {
    return <SwipingCards />;
  }, []);

  if (isLoading) {
    return (
      <div className="mx-auto mt-8 flex min-h-[calc(100vh-var(--header-height)-var(--footer-height))] w-full grow flex-col items-center justify-center gap-2">
        <LoadingSpinner />
        <p className="text-muted-foreground">
          Wir berechnen deine Ergebnisse...
        </p>
      </div>
    );
  }

  return swipingCards;
}

export default WahlSwiper;
