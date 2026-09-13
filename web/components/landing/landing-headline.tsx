'use client';

import { cn } from '@/lib/utils';
import { useReducedMotion } from 'motion/react';
import { Instrument_Serif } from 'next/font/google';
import { useEffect, useState } from 'react';

const headlineSerif = Instrument_Serif({
  subsets: ['latin'],
  weight: '400',
  style: 'italic',
  display: 'swap',
});

const PHRASES = [
  'Politik verstehen.',
  'Positionen vergleichen.',
  'Klarer entscheiden.',
];

function LandingHeadline({ isEditing }: { isEditing: boolean }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (reducedMotion || isEditing) return;

    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        setActiveIndex((index) => (index + 1) % PHRASES.length);
      }
    }, 4500);
    return () => window.clearInterval(interval);
  }, [reducedMotion, isEditing]);

  return (
    <div className="relative w-full">
      <h1 className="text-balance text-[1.875rem] font-semibold leading-[1.1] tracking-[-0.045em] sm:text-5xl md:text-6xl">
        Deine Frage zählt.
        <span className="sr-only"> Politik verstehen.</span>
        <span
          aria-hidden="true"
          className={cn(
            headlineSerif.className,
            'mt-3 grid text-[2.1rem] font-normal italic tracking-[-0.02em] text-[#ED3833] sm:text-[3.36rem] md:text-[4.2rem]',
          )}
        >
          {PHRASES.map((phrase, index) => (
            <span
              key={phrase}
              className="pointer-events-none col-start-1 row-start-1 whitespace-nowrap"
            >
              {phrase.split(' ').map((word, wordIndex) => {
                const isActive = index === (reducedMotion ? 0 : activeIndex);

                return (
                  <span
                    key={word}
                    className={cn(
                      'inline-block whitespace-pre transition-[opacity,filter,transform] ease-out motion-reduce:transition-none',
                      isActive ? 'opacity-100 blur-0' : 'opacity-0 blur-[5px]',
                    )}
                    style={{
                      transform: reducedMotion
                        ? 'none'
                        : isActive
                          ? 'translateY(0)'
                          : index ===
                              (activeIndex + PHRASES.length - 1) %
                                PHRASES.length
                            ? 'translateY(-8px)'
                            : 'translateY(8px)',
                      transitionDuration: isActive ? '400ms' : '220ms',
                      transitionDelay: `${isActive ? 180 + wordIndex * 120 : wordIndex * 60}ms`,
                    }}
                  >
                    {wordIndex > 0 ? ` ${word}` : word}
                  </span>
                );
              })}
            </span>
          ))}
        </span>
      </h1>
    </div>
  );
}

export default LandingHeadline;
