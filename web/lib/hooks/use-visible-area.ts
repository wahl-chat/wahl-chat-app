'use client';

import { useEffect, useState } from 'react';

export type VisibleArea = { top: number; height: number };

/**
 * The part of the layout viewport the on-screen keyboard leaves visible, or
 * null while nothing covers it. iOS keeps fixed elements at full height under
 * the keyboard and pans the page instead; a fixed view sized to this area
 * ends right on top of the keyboard.
 */
export function useVisibleArea(): VisibleArea | null {
  const [area, setArea] = useState<VisibleArea | null>(null);
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const update = () => {
      const covered = window.innerHeight - viewport.height > 1;
      setArea(
        covered ? { top: viewport.offsetTop, height: viewport.height } : null,
      );
    };
    update();
    viewport.addEventListener('resize', update);
    viewport.addEventListener('scroll', update);
    return () => {
      viewport.removeEventListener('resize', update);
      viewport.removeEventListener('scroll', update);
    };
  }, []);
  return area;
}
