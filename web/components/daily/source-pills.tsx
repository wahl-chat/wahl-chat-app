'use client';

import ChatMessageReference from '@/components/chat/chat-message-reference';
import { useMediaViewer } from '@/components/providers/media-viewer-provider';
import {
  type NumberedSources,
  isVideoSource,
  sourceTooltip,
  toViewerSource,
} from '@/lib/daily/sources';

/**
 * The chat's citation pills after a bullet or position: "Video 2" opens the
 * speech at the passage, a bare number the protocol page with the sentence
 * highlighted, both in the app's media viewer.
 */
export function SourcePills({
  numbers,
  sources,
}: {
  /** 1-based, as `numberedSources` hands them out. */
  numbers: number[];
  sources: NumberedSources;
}) {
  const viewer = useMediaViewer();
  if (numbers.length === 0) {
    return null;
  }
  // The pill counts from 0, like the chat's sources.
  const at = (index: number) => sources.sources[index];
  const open = (index: number) => {
    const source = at(index);
    if (!source) {
      return;
    }
    const target = toViewerSource(source);
    if (viewer) {
      viewer.openSource(target);
    } else if (target.url) {
      window.open(target.url, '_blank', 'noopener,noreferrer');
    }
  };
  return (
    <>
      {' '}
      <ChatMessageReference
        numbers={numbers.map((n) => String(n - 1))}
        index={0}
        onReferenceClick={open}
        getReferenceName={(index) => (at(index) ? String(index + 1) : null)}
        getReferenceTooltip={(index) => {
          const source = at(index);
          return source ? sourceTooltip(source) : null;
        }}
        getReferenceIsVideo={(index) => {
          const source = at(index);
          return source ? isVideoSource(source) : false;
        }}
      />
    </>
  );
}
