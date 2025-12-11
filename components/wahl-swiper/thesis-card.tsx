import { cn } from '@/lib/utils';
import {
  motion,
  useAnimate,
  useMotionValue,
  useTransform,
  type PanInfo,
} from 'motion/react';
import { useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { ArrowLeftIcon } from 'lucide-react';
import type { Thesis } from '@/lib/wahl-swiper/wahl-swiper-store.types';
import type { SwipeType } from '@/lib/wahl-swiper/wahl-swiper.types';

export type Props = {
  card: Thesis;
  active: boolean;
  canGoBack: boolean;
  removeCard: (swipe: SwipeType) => void;
  handleBack: () => void;
};

function ThesisCard({
  card,
  removeCard,
  active,
  canGoBack,
  handleBack,
}: Props) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const [scope, animate] = useAnimate();

  const backgroundGradient = useTransform(() => {
    const latestX = x.get();
    const latestY = y.get();
    const angleRad = Math.atan2(latestY, latestX);
    const angleDeg = (90 + (angleRad * 180) / Math.PI) % 360;
    const dragDistance = Math.sqrt(latestX ** 2 + latestY ** 2);
    const maxDistance = 100;
    const progress = Math.min(dragDistance / maxDistance, 1);

    const directionThreshold = 100;
    const directionFactor = Math.min(Math.abs(latestX) / directionThreshold, 1);
    let baseColor = '255,255,255';
    if (latestX < 0) {
      const r = 255;
      const g = Math.round(255 * (1 - directionFactor));
      const b = Math.round(255 * (1 - directionFactor));
      baseColor = `${r},${g},${b}`;
    } else if (latestX > 0) {
      const g = 255;
      const r = Math.round(255 * (1 - directionFactor));
      const b = Math.round(255 * (1 - directionFactor));
      baseColor = `${r},${g},${b}`;
    }

    const stop1 = -50 * progress;
    const midStop = (stop1 + 100) / 2;
    const opacity = progress;
    const midOpacity = opacity * 0.5;

    return `linear-gradient(${angleDeg}deg, rgba(${baseColor}, 0.0) ${stop1}%, rgba(${baseColor}, ${midOpacity}) ${midStop}%, rgba(${baseColor}, ${opacity}) 100%)`;
  });

  const onDragEnd = async (_e: unknown, info: PanInfo) => {
    if (info.offset.y < -100 && info.velocity.y <= 0) {
      manuallyRemoveCard('skip');
      return;
    }
    if (info.offset.x > 100 && info.velocity.x >= 0) {
      manuallyRemoveCard('yes');
      return;
    }
    if (info.offset.x < -100 && info.velocity.x <= 0) {
      manuallyRemoveCard('no');
      return;
    }
    // If none of the conditions are met (or the velocity doesn't match), do nothing.
  };

  const manuallyRemoveCard = useCallback(
    async (direction: SwipeType) => {
      const animatedRemoveCard = async () => {
        const currentX = x.get();
        const currentY = y.get();
        let angle = Math.atan2(currentY, currentX);
        const distance = 300;

        if (currentX === 0 && currentY === 0) {
          angle =
            direction === 'skip'
              ? -Math.PI / 2
              : direction === 'yes'
                ? 0
                : Math.PI;
        }

        await animate(
          scope.current,
          {
            x: Math.cos(angle) * distance,
            y: Math.sin(angle) * distance,
            opacity: 0,
            scale: 0.9,
          },
          { duration: 0.2, ease: 'easeOut' },
        );
      };

      await animatedRemoveCard();
      removeCard(direction);
    },
    [x, y, scope, animate, removeCard],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!active) return;
    if (e.key === 'ArrowLeft') {
      manuallyRemoveCard('no');
    } else if (e.key === 'ArrowRight') {
      manuallyRemoveCard('yes');
    } else if (e.key === 'ArrowDown') {
      manuallyRemoveCard('skip');
    }
  };

  const classNames = cn(
    'absolute inset-0 flex cursor-grab flex-col justify-center rounded-2xl',
    'bg-zinc-50 dark:bg-zinc-900 gap-2',
  );

  const content = (
    <>
      <h1 className="text-xs text-muted-foreground">{card.topic}</h1>
      <p className="font-semibold">{card.question}</p>
    </>
  );

  const commonClassNames = cn(classNames, 'text-foreground h-full');

  const BackButton = (
    <Button
      variant="ghost"
      size="icon"
      className="absolute left-2 top-2 size-8 text-xs text-muted-foreground"
      onClick={handleBack}
      disabled={!active}
    >
      <ArrowLeftIcon className="size-4" />
    </Button>
  );

  return (
    <motion.div
      id={card.id}
      key={card.id}
      ref={scope}
      drag={active}
      dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
      onDragEnd={onDragEnd}
      initial={{ scale: active ? 1 : 0.95, x: 0, y: 0 }}
      animate={{ scale: active ? 1 : 0.95, x: 0, y: 0 }}
      style={{
        x,
        y,
      }}
      whileTap={{ cursor: 'grabbing' }}
      className={cn(commonClassNames, 'border border-border')}
      tabIndex={active ? 0 : -1}
      onKeyDown={handleKeyDown}
    >
      <motion.div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          borderRadius: 'inherit',
          background: backgroundGradient,
          zIndex: 0,
        }}
        tabIndex={-1}
      />
      <div
        className={cn(
          commonClassNames,
          'inset-1 w-auto h-auto shadow-none rounded-[13px] p-4',
        )}
        tabIndex={-1}
      >
        {content}

        {canGoBack && BackButton}
      </div>
    </motion.div>
  );
}

export default ThesisCard;
