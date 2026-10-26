'use client';

import ContextSwitcher from '@/components/context/context-switcher';

function WahlSwiperContextSelector() {
  return (
    <ContextSwitcher
      buildHref={(contextId) => `/${contextId}/swiper`}
      area="swiper"
      filter={(context) => context.supports_swiper}
    />
  );
}

export default WahlSwiperContextSelector;
