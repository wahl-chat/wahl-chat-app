'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import LoadingSpinner from '@/components/loading-spinner';
import { useWahlSwiperStore } from '@/components/providers/wahl-swiper-store-provider';
import { useRouter } from '@/i18n/navigation';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { captureProlificParams } from '@/lib/prolific-study/prolific-metadata';
import { useTranslations } from 'next-intl';
import { useSearchParams } from 'next/navigation';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import SwipingCards from './swiping-cards';

function WahlSwiper() {
  const t = useTranslations('swiper.swiper');
  const [isLoading, setIsLoading] = useState(false);
  const finished = useWahlSwiperStore(
    (state) => state.thesesStack.length === 0,
  );
  const saveSwiperHistory = useWahlSwiperStore(
    (state) => state.saveSwiperHistory,
  );
  const contextId = useWahlSwiperStore((state) => state.contextId);
  const setProlificMetadata = useWahlSwiperStore(
    (state) => state.setProlificMetadata,
  );

  const { user } = useAnonymousAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Capture Prolific URL Params on mount
  useEffect(() => {
    const metadata = captureProlificParams(searchParams);
    if (metadata) {
      setProlificMetadata(metadata);
    }
  }, []);

  const handleFinished = useCallback(async () => {
    const errorToast = () => toast.error(t('resultsError'));

    if (!user) {
      errorToast();
      return;
    }

    setIsLoading(true);

    try {
      const resultId = await saveSwiperHistory(user.uid);
      router.push(
        `/${contextId ?? DEFAULT_CONTEXT_ID}/swiper/results/${resultId}`,
      );
    } catch (error) {
      console.error(error);
      errorToast();
      setIsLoading(false);
    }
  }, [user, router, saveSwiperHistory, contextId, t]);

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
        <p className="text-muted-foreground">{t('calculating')}</p>
      </div>
    );
  }

  return swipingCards;
}

export default WahlSwiper;
