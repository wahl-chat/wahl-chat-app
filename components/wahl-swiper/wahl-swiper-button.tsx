import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { SwipeType } from '@/lib/wahl-swiper/wahl-swiper.types';
import { ChevronsRightIcon, HeartIcon, XIcon } from 'lucide-react';
import { useState } from 'react';
import WahlSwiperSkipButton from './wahl-swiper-skip-button';

type Props = {
  type: SwipeType;
  onClick: () => void;
};

export type WahlSwiperButtonVariant = {
  icon: React.ReactNode;
  hover: string;
  normal: string;
  tooltip?: string;
};

function WahlSwiperButton({ type, onClick }: Props) {
  const [clicked, setClicked] = useState(false);

  const variants: Record<SwipeType, WahlSwiperButtonVariant> = {
    yes: {
      icon: <HeartIcon className="size-4" />,
      hover:
        'bg-green-500 border-green-200 dark:border-green-700 md:hover:bg-green-400 md:hover:border-green-200 md:dark:hover:border-green-600 hover:text-green-50 hover:bg-green-500 text-green-50',
      normal:
        'bg-green-400 hover:bg-green-400 hover:text-green-50 text-green-50 scale-[1.18] border-green-200 dark:border-green-700 md:border-[5px]',
    },
    no: {
      icon: <XIcon className="size-4" />,
      hover:
        'bg-red-500 border-red-400 dark:border-red-700 md:hover:bg-red-400 md:hover:border-red-200 md:dark:hover:border-red-600 hover:text-red-50 hover:bg-red-500 text-red-50',
      normal:
        'bg-red-400 hover:bg-red-400 hover:text-red-50 text-red-50 scale-[1.18] border-red-200 dark:border-red-700 md:border-[5px]',
    },
    skip: {
      icon: <ChevronsRightIcon className="size-4 text-gray-500" />,
      hover:
        'md:hover:bg-gray-500/10 md:hover:border-gray-500/20 hover:bg-transparent border size-10',
      normal:
        'bg-gray-500/20 border-gray-500 hover:bg-gray-500/20 border scale-100 hover:scale-100 md:hover:scale-100',
      tooltip: 'Überspringen',
    },
  };

  const handleClick = () => {
    setClicked(true);
    onClick();

    setTimeout(() => {
      setClicked(false);
    }, 500);
  };

  if (type === 'skip') {
    return (
      <WahlSwiperSkipButton
        variant={variants[type]}
        clicked={clicked}
        onClick={handleClick}
      />
    );
  }

  return (
    <Button
      variant="outline"
      className={cn(
        'size-14 rounded-full transition-all duration-200 border-4 md:hover:scale-[1.18] ease-in-out',
        !clicked && variants[type].hover,
        clicked && variants[type].normal,
      )}
      tooltip={variants[type].tooltip}
      onClick={handleClick}
    >
      {variants[type].icon}
    </Button>
  );
}

export default WahlSwiperButton;
