'use client';

import { useEffect, useRef } from 'react';

import SkipLink from '@/components/skip-link';
import type { LeafCloseInfo } from '@/modules/guided-exploration/hooks/use-leaf-close-flow';

interface LeafCloseAnnouncerProps {
  info: LeafCloseInfo | null;
}

/**
 * Renders the post-close feedback for the leaf sidebar: a persistent live
 * region that announces where the user landed, plus a self-describing
 * skip-link (next topic, or chat input when all topics are explored) which
 * receives focus so the user has an immediate next step.
 */
export function LeafCloseAnnouncer({ info }: LeafCloseAnnouncerProps) {
  const linkRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    if (!info) return;
    // rAF so focus lands after the sheet has finished tearing down (its
    // onCloseAutoFocus is prevented, so nothing fights us for focus).
    const id = requestAnimationFrame(() => linkRef.current?.focus());
    return () => cancelAnimationFrame(id);
    // key changes on every close, including repeat closes of the same leaf.
  }, [info?.key]);

  return (
    <>
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {info?.announcement ?? ''}
      </div>
      {info && (
        <SkipLink ref={linkRef} href={info.skip.href}>
          {info.skip.label}
        </SkipLink>
      )}
    </>
  );
}
