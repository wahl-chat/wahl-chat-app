'use client';

import { isProlificStudy } from '@/lib/study/prolific-params';
import { useEffect, useState } from 'react';
import WahlSwiperExperimentalDisclaimer from './wahl-swiper-experimental-disclaimer';
import WahlSwiperProlificDisclaimer from './wahl-swiper-prolific-disclaimer';

function WahlSwiperDisclaimerWrapper() {
  const [isProlific, setIsProlific] = useState<boolean | null>(null);

  // Check after mount to avoid hydration mismatch
  useEffect(() => {
    setIsProlific(isProlificStudy());
  }, []);

  // Don't render until we know which disclaimer to show
  if (isProlific === null) {
    return null;
  }

  if (isProlific) {
    return <WahlSwiperProlificDisclaimer />;
  }

  return <WahlSwiperExperimentalDisclaimer />;
}

export default WahlSwiperDisclaimerWrapper;
