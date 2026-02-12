'use client';

import ContextSwitcher from '@/components/context/context-switcher';

function WahlSwiperContextSelector() {
  return (
    <ContextSwitcher
      buildHref={(contextId) => `/${contextId}/swiper`}
      navigationTargetLabel="zum Wahl-Swiper weitergeleitet"
      currentAreaLabel="den aktuellen Wahl-Swiper"
      filter={(context) => context.supports_swiper}
    />
  );
}

export default WahlSwiperContextSelector;
