import { Button } from '@/components/ui/button';
import { useCarousel } from '@/components/ui/carousel';
import type { PartyDetails } from '@/lib/party-details';
import { scrollToCarouselContainerBottom } from '@/lib/scroll-utils';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import Image from 'next/image';
import { useCallback, useEffect, useRef, useState } from 'react';

type Props = {
  parties: PartyDetails[];
  containerId: string;
};

function ChatGroupSlideCounter({ parties, containerId }: Props) {
  const { api } = useCarousel();
  const firstRender = useRef(true);

  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    if (!api) return;

    const onReInit = () => {
      setSelectedIndex(api.selectedScrollSnap());
    };

    const onSelect = () => {
      setSelectedIndex(api.selectedScrollSnap());

      if (firstRender.current) {
        firstRender.current = false;
        return;
      }

      scrollToCarouselContainerBottom(containerId);
    };

    onSelect();
    api.on('reInit', () => onReInit()).on('select', () => onSelect());
  }, [api]);

  const scrollTo = useCallback(
    (index: number) => {
      if (!api) return;

      api.scrollTo(index);
    },
    [api],
  );

  return (
    <div className="flex flex-row items-center justify-center gap-2">
      {parties.map((party, index) => (
        <Button
          key={party.party_id}
          className={cn(
            'size-5 rounded-full bg-zinc-300 overflow-hidden flex items-center justify-center hover:bg-zinc-300 transition-all duration-300 relative',
            selectedIndex === index &&
              'ring-2 ring-zinc-900 dark:ring-zinc-100 ring-offset-2',
          )}
          style={{
            background: party.background_color,
          }}
          onClick={() => scrollTo(index)}
          size="icon"
        >
          <Image
            src={buildPartyImageUrl(party.party_id)}
            alt={party.name}
            sizes="20px"
            fill
            className="object-contain"
          />
        </Button>
      ))}
    </div>
  );
}

export default ChatGroupSlideCounter;
