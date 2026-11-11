'use client';

import type { DigestSessionSection } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { Loader2Icon, PlayIcon } from 'lucide-react';
import { useRef, useState } from 'react';

// The same speech can sit in the feed and in the open detail at once; starting
// one pauses the other rather than playing both over each other.
let playingElement: HTMLMediaElement | null = null;

// Past the black first frames, as the feed job does when it has no start.
const FALLBACK_START = 0.5;

type Media = {
  kind: 'video' | 'audio';
  /** For video, a media fragment at the second playback starts. */
  src: string;
  /** A still of the frame at that very second; null shows a dark frame. */
  poster: string | null;
  badge: string;
  caption: string | null;
};

function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

function startCaption(label: string, start: number) {
  return Math.floor(start) > 0 ? `${label} · ab ${formatTime(start)}` : label;
}

/**
 * The feed job chooses the speech and its start, and cuts the poster at that
 * start, so the card plays on from the frame it shows. Nothing is chosen
 * here: a second rule on this side would show one frame and play another.
 */
export function sectionMedia(section: DigestSessionSection): Media | null {
  if (section.audio) {
    const { duration_seconds: duration } = section.audio;
    return {
      kind: 'audio',
      src: section.audio.url,
      poster: null,
      badge: duration ? `Audio · ${formatTime(duration)}` : 'Audio',
      caption: section.audio.title,
    };
  }
  const card = section.card_video;
  if (card) {
    const label =
      card.speaker && card.party_name
        ? `${card.speaker} (${card.party_name})`
        : card.speaker;
    return {
      kind: 'video',
      src: `${card.video_url}#t=${card.start}`,
      poster: card.poster_url,
      badge: 'Video',
      caption: label ? startCaption(label, card.start) : null,
    };
  }
  return section.video_url
    ? {
        kind: 'video',
        src: `${section.video_url.split('#')[0]}#t=${FALLBACK_START}`,
        poster: null,
        badge: 'Video',
        caption: null,
      }
    : null;
}

/**
 * Dark 16:9 frame with a play button; native controls once playing. Nothing
 * of the media loads before play: a poster stands in for the first frame
 * and stays on top until the video paints, which is the same image, so the
 * switch does not flash. In a feed card, the play button and the playing
 * media sit above the card's stretched link (z-10), so they play rather than
 * open the detail.
 */
export function SectionMediaFrame({
  media,
  className,
  mediaClassName,
  small = false,
}: {
  media: Media;
  className?: string;
  /** On the video until it plays, e.g. a card's hover zoom. */
  mediaClassName?: string;
  small?: boolean;
}) {
  const ref = useRef<HTMLMediaElement | null>(null);
  const [started, setStarted] = useState(false);
  const [painted, setPainted] = useState(false);

  // The poster covers the native controls until the video paints, so a play
  // that fails must bring the play button back rather than leave a still.
  const stop = () => setStarted(false);
  const play = () => {
    setStarted(true);
    ref.current?.play().catch((error: unknown) => {
      console.error(`[media] Could not play ${media.src}:`, error);
      stop();
    });
  };
  const onPlay = () => {
    if (playingElement && playingElement !== ref.current) {
      playingElement.pause();
    }
    playingElement = ref.current;
  };

  return (
    <div
      className={cn(
        'relative aspect-video w-full overflow-hidden bg-zinc-800',
        className,
      )}
    >
      {media.kind === 'video' ? (
        <video
          ref={(el) => {
            ref.current = el;
          }}
          src={media.src}
          preload="none"
          playsInline
          controls={started}
          onPlay={onPlay}
          onPlaying={() => setPainted(true)}
          onError={stop}
          className={cn(
            'absolute inset-0 size-full object-cover',
            // Playing, the controls must stay put under the pointer.
            started ? 'z-10' : mediaClassName,
          )}
        />
      ) : (
        <audio
          ref={(el) => {
            ref.current = el;
          }}
          src={media.src}
          preload="metadata"
          controls={started}
          onPlay={onPlay}
          className={cn(
            'absolute inset-x-3 bottom-3 w-[calc(100%-1.5rem)]',
            started && 'z-10',
          )}
        />
      )}
      {media.poster && !painted && (
        // A plain <img>, not the video's poster attribute: that one loads
        // with the page, this one only once the card nears the viewport.
        <img
          src={media.poster}
          alt=""
          loading="lazy"
          decoding="async"
          className={cn(
            'pointer-events-none absolute inset-0 size-full object-cover',
            started ? 'z-10' : mediaClassName,
          )}
        />
      )}
      {media.poster && started && !painted && (
        <Loader2Icon
          aria-hidden
          className="pointer-events-none absolute left-1/2 top-1/2 z-10 size-8 -translate-x-1/2 -translate-y-1/2 animate-spin text-white"
        />
      )}
      {!started && (
        <>
          <span className="absolute left-3 top-3 rounded-md bg-zinc-100 px-2 py-0.5 text-[13px] font-semibold text-zinc-900">
            {media.badge}
          </span>
          <button
            type="button"
            onClick={play}
            aria-label={
              media.kind === 'video' ? 'Rede abspielen' : 'Audio abspielen'
            }
            className={cn(
              'absolute left-1/2 top-1/2 z-10 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-800',
              small ? 'size-10' : 'size-14',
            )}
          >
            <PlayIcon className="ml-0.5 size-5" fill="currentColor" />
          </button>
          {media.caption && !small && (
            <span className="absolute inset-x-3 bottom-3 truncate text-[13px] text-white">
              {media.caption}
            </span>
          )}
        </>
      )}
    </div>
  );
}
