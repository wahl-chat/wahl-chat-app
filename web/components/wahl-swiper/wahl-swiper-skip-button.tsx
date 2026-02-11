import { useWahlSwiperStore } from '@/components/providers/wahl-swiper-store-provider';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import * as RadixPopover from '@radix-ui/react-popover';
import { ChevronsRightIcon, MessageCircleMoreIcon } from 'lucide-react';
import type { WahlSwiperButtonVariant } from './wahl-swiper-button';
import {useEffect, useState} from "react";
import {isProlificStudy} from "@/lib/prolific-study/prolific-metadata";

type Props = {
  variant: WahlSwiperButtonVariant;
  clicked: boolean;
  onClick: () => void;
};

function WahlSwiperSkipButton({ variant, clicked, onClick }: Props) {
  const expandChat = useWahlSwiperStore((state) => state.setChatIsExpanded);
  const showSkipDisclaimer = useWahlSwiperStore(
    (state) => state.showSkipDisclaimer,
  );
  const setShowSkipDisclaimer = useWahlSwiperStore(
    (state) => state.setShowSkipDisclaimer,
  );
  const disclaimerShown = useWahlSwiperStore(
    (state) => state.skipDisclaimerShown,
  );
  const setSkipDisclaimerShown = useWahlSwiperStore(
    (state) => state.setSkipDisclaimerShown,
  );
  const [hideSkipButtonPopup, setHideSkipButtonPopup] = useState(false);

  useEffect(() => {
    if (isProlificStudy()) {
      setHideSkipButtonPopup(true);
    }
  }, [])

  const handleClick = () => {
    if (disclaimerShown) {
      return onClick();
    }

    setShowSkipDisclaimer(!showSkipDisclaimer);
    setSkipDisclaimerShown(true);
  };

  const handleStartChat = () => {
    setShowSkipDisclaimer(false);
    expandChat(true);
  };

  const handleSkip = () => {
    setShowSkipDisclaimer(false);
    onClick();
  };

  if (hideSkipButtonPopup) {
    return getSkipButton({ variant, clicked, onClick });
  }

  return (
    <Popover open={showSkipDisclaimer} onOpenChange={setSkipDisclaimerShown}>
      <RadixPopover.Anchor asChild>
        {getSkipButton({ variant, clicked, onClick }, handleClick)}
      </RadixPopover.Anchor>

      <PopoverContent side="top" sideOffset={12}>
        <h1 className="font-bold">Willst du mehr über die These erfahren?</h1>
        <p className="text-sm text-muted-foreground">
          Nutze unseren <span className="font-bold">Chat</span> um mehr über die
          These zu erfahren und eine{' '}
          <span className="font-bold">bessere Entscheidung</span> zu treffen.
        </p>
        <div className="mt-2 flex justify-center gap-2">
          <Button size="sm" className="grow" onClick={handleStartChat}>
            <MessageCircleMoreIcon className="size-4" />
            Chat starten
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="aspect-square"
            onClick={handleSkip}
          >
            <ChevronsRightIcon className="size-4" />
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function getSkipButton(
    { variant, clicked, onClick }: Props,
    handleClick?: () => void,
) {
  return (
      <Button
          variant="outline"
          className={cn(
              'size-14 rounded-full transition-all duration-200 border-4 md:hover:scale-[1.18] ease-in-out',
              !clicked && variant.hover,
              clicked && variant.normal,
          )}
          onClick={handleClick ? handleClick : onClick}
      >
        {variant.icon}
      </Button>
  );
}

export default WahlSwiperSkipButton;
