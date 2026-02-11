import { useCarousel } from '@/components/ui/carousel';
import { useEffect, useState } from 'react';

function useCarouselCurrentIndex() {
  const { api } = useCarousel();

  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    if (!api) return;

    const onReInit = () => {
      setSelectedIndex(api.selectedScrollSnap());
    };

    const onSelect = () => {
      setSelectedIndex(api.selectedScrollSnap());
    };

    onSelect();
    api.on('reInit', () => onReInit()).on('select', () => onSelect());
  }, [api]);

  return selectedIndex;
}

export default useCarouselCurrentIndex;
