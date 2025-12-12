import { cn } from '@/lib/utils';
import { useEffect, useRef, useState } from 'react';

type Props = {
  children: React.ReactNode;
  className?: string;
};

function AnimateTextOverflow({ children, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [animationStyle, setAnimationStyle] = useState<React.CSSProperties>({});

  const scrollPaddingStart = 50;
  const scrollPaddingEnd = 50;

  useEffect(() => {
    if (!containerRef.current || !textRef.current) return;

    const calculateOverflow = () => {
      const textRefCurrent = textRef.current;
      const containerRefCurrent = containerRef.current;

      if (!textRefCurrent || !containerRefCurrent) return;

      const textWidth = textRefCurrent.scrollWidth;
      const containerWidth = containerRefCurrent.clientWidth;

      if (textWidth > containerWidth) {
        setIsOverflowing(true);
        const overflowDistance = textWidth - containerWidth;
        const totalScrollDistance =
          overflowDistance + scrollPaddingStart + scrollPaddingEnd;
        const baseSpeed = 50; // pixels per second
        const duration = totalScrollDistance / baseSpeed; // seconds

        setAnimationStyle({
          '--scroll-distance': `-${totalScrollDistance}px`,
          '--scroll-duration': `${duration}s`,
        } as React.CSSProperties);
      } else {
        setIsOverflowing(false);
        setAnimationStyle({});
      }
    };

    calculateOverflow();

    window.addEventListener('resize', calculateOverflow);
    return () => {
      window.removeEventListener('resize', calculateOverflow);
    };
  }, [children, scrollPaddingStart, scrollPaddingEnd]);

  return (
    <div
      className={cn('w-full overflow-hidden h-8 relative', className)}
      ref={containerRef}
    >
      {isOverflowing ? (
        <>
          <div
            className="pointer-events-none absolute inset-0 z-20 before:absolute before:left-0 before:top-0 before:h-full before:w-1/6 
        before:bg-gradient-to-r before:from-background before:to-transparent after:absolute after:right-0 
        after:top-0 after:h-full after:w-1/6 after:bg-gradient-to-l after:from-background after:to-transparent"
          />
          <h1
            className="animate-scroll absolute left-0 top-0 whitespace-nowrap text-xl font-bold"
            ref={textRef}
            style={{
              ...animationStyle,
              paddingLeft: `${scrollPaddingStart}px`,
              paddingRight: `${scrollPaddingEnd}px`,
            }}
          >
            {children}
          </h1>
        </>
      ) : (
        <h1
          className="absolute inset-x-0 top-0 whitespace-nowrap text-center text-xl font-bold"
          ref={textRef}
        >
          {children}
        </h1>
      )}
    </div>
  );
}

export default AnimateTextOverflow;
