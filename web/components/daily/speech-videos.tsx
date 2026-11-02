'use client';

import { sortBySeating } from '@/lib/daily/seating-order';
import type { DigestSessionSection } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { PlayIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useRef, useState } from 'react';

// The same speech can sit in the feed and in the open detail at once; starting
// one pauses the other rather than playing both over each other.
let playingElement: HTMLMediaElement | null = null;

type Media = {
  kind: 'video' | 'audio';
  /** For video, a media fragment at the speech's start. */
  src: string;
  badge: string;
  caption: string | null;
};

function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

/**
 * The video file opened at a media fragment: the frame there doubles as the
 * thumbnail, which is why preload is "metadata" rather than "none" (that leaves
 * an empty box until playback starts).
 */
function videoSrc(videoUrl: string, link: string | null | undefined): string {
  const start = Number((link ?? '').split('#t=')[1]);
  return `${videoUrl.split('#')[0]}#t=${Number.isFinite(start) && start > 0.5 ? start : 0.5}`;
}

/** Formats "speaker · from 1:23" in the reader's language. */
export type StartCaption = (speaker: string, time: string) => string;

function startCaption(
  speaker: string,
  link: string | null | undefined,
  caption: StartCaption,
) {
  const start = Number((link ?? '').split('#t=')[1]);
  return Number.isFinite(start) && start > 0
    ? caption(speaker, formatTime(start))
    : speaker;
}

/**
 * One speech stands for the debate: the opening speaker's when known, since
 * the opening statement quotes it; otherwise the first Fraktion's in seating
 * order that has video, then any cited speech video, then the agenda item's.
 */
export function sectionMedia(
  section: DigestSessionSection,
  caption: StartCaption,
): Media | null {
  if (section.audio) {
    const { duration_seconds: duration } = section.audio;
    return {
      kind: 'audio',
      src: section.audio.url,
      badge: duration ? `Audio · ${formatTime(duration)}` : 'Audio',
      caption: section.audio.title,
    };
  }
  const speakers = sortBySeating(section.positions ?? []).flatMap((p) =>
    p.speakers
      .filter((s) => s.video_url)
      .map((s) => ({ ...s, party: p.party_name })),
  );
  const opener = section.opening_quote?.speaker;
  const speaker =
    speakers.find((s) => s.name === opener) ?? speakers.at(0) ?? null;
  if (speaker?.video_url) {
    return {
      kind: 'video',
      src: videoSrc(speaker.video_url, speaker.video_link),
      badge: 'Video',
      caption: startCaption(
        `${speaker.name} (${speaker.party})`,
        speaker.video_link,
        caption,
      ),
    };
  }
  const cited = section.citations.find((c) => c.video_url);
  if (cited?.video_url) {
    return {
      kind: 'video',
      src: videoSrc(cited.video_url, cited.url),
      badge: 'Video',
      caption: cited.speaker ?? null,
    };
  }
  return section.video_url
    ? {
        kind: 'video',
        src: videoSrc(section.video_url, null),
        badge: 'Video',
        caption: null,
      }
    : null;
}

/** Dark 16:9 frame with a play button; native controls once playing. */
export function SectionMediaFrame({
  media,
  className,
  small = false,
}: {
  media: Media;
  className?: string;
  small?: boolean;
}) {
  const t = useTranslations('feed');
  const ref = useRef<HTMLMediaElement | null>(null);
  const [started, setStarted] = useState(false);

  const play = () => {
    setStarted(true);
    ref.current?.play().catch((error: unknown) => {
      console.error(`[media] Could not play ${media.src}:`, error);
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
          preload="metadata"
          playsInline
          controls={started}
          onPlay={onPlay}
          className="absolute inset-0 size-full object-cover"
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
          className="absolute inset-x-3 bottom-3 w-[calc(100%-1.5rem)]"
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
              media.kind === 'video' ? t('playSpeech') : t('playAudio')
            }
            className={cn(
              'absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white text-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-800',
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
