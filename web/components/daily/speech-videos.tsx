'use client';

import { sortBySeating } from '@/lib/daily/seating-order';
import type {
  DigestCitation,
  DigestSessionSection,
} from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { useEffect, useRef } from 'react';
import { CarouselDots, useSnapCarousel } from './carousel';
import { PartyMark } from './party-positions';
import { SourceLink } from './vote-panels';

const VIDEO_FRAME =
  'aspect-video w-full rounded-[4px] border-2 border-[var(--daily-ink)] bg-black shadow-[4px_4px_0_0_var(--daily-ink)]';

const SLIDE_GAP = 16;

type VideoSlide = {
  key: string;
  partyId: string | null;
  color: string | null;
  speaker: string;
  label: string;
  /** Video file, with a media fragment at the speech's start. */
  src: string;
  /** Where the caption links to. */
  href: string;
};

/**
 * The video file opened at a media fragment: the frame there doubles as the
 * thumbnail, which is why preload is "metadata" rather than "none" (that leaves
 * an empty grey box until playback starts).
 */
function videoSrc(videoUrl: string, link: string | null | undefined): string {
  const start = Number((link ?? '').split('#t=')[1]);
  return `${videoUrl.split('#')[0]}#t=${Number.isFinite(start) && start > 0.5 ? start : 0.5}`;
}

/** One speaker per Fraktion, in the order the positions are listed. */
function representativeSlides(section: DigestSessionSection): VideoSlide[] {
  const slides: VideoSlide[] = [];
  for (const position of sortBySeating(section.positions ?? [])) {
    const speaker = position.speakers.find((s) => s.video_url);
    if (!speaker?.video_url) {
      continue;
    }
    slides.push({
      key: `${position.party_id}:${speaker.name}`,
      partyId: position.party_id,
      color: position.color,
      speaker: speaker.name,
      label: `${speaker.name} (${position.party_name}) · Video der Rede`,
      src: videoSrc(speaker.video_url, speaker.video_link),
      href: speaker.video_link ?? speaker.video_url,
    });
  }
  return slides;
}

/** Digests built before speakers carried their own video. */
function citationSlides(citations: DigestCitation[]): VideoSlide[] {
  return citations
    .filter((c) => c.video_url)
    .map((c) => ({
      key: c.url,
      partyId: c.party_id ?? null,
      color: c.color ?? null,
      speaker: c.speaker ?? c.title,
      label: c.title,
      src: videoSrc(c.video_url as string, c.url),
      href: c.url,
    }));
}

function SlideCaption({ slide }: { slide: VideoSlide }) {
  return (
    <span className="flex items-center gap-2">
      {slide.partyId && slide.color && (
        <PartyMark
          partyId={slide.partyId}
          color={slide.color}
          className="size-6 border-[1.5px] p-0.5"
        />
      )}
      <SourceLink href={slide.href}>{slide.label}</SourceLink>
    </span>
  );
}

function VideoCarousel({ slides }: { slides: VideoSlide[] }) {
  const { ref, active, onScroll, goTo } = useSnapCarousel(SLIDE_GAP);
  const players = useRef<(HTMLVideoElement | null)[]>([]);
  const several = slides.length > 1;

  // Swiping away from a playing speech stops it, so two never play at once.
  useEffect(() => {
    players.current.forEach((player, i) => {
      if (i !== active && player && !player.paused) {
        player.pause();
      }
    });
  }, [active]);

  return (
    <div className="flex flex-col gap-2">
      <div
        ref={ref}
        onScroll={onScroll}
        // Padding keeps the frames' offset shadows inside the scroll box.
        className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-2 pr-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {slides.map((slide, i) => (
          <figure
            key={slide.key}
            className={cn(
              'flex shrink-0 snap-start flex-col gap-2',
              // The next video peeks in, so the strip reads as swipeable.
              several ? 'w-[92%]' : 'w-full',
            )}
          >
            <video
              ref={(el) => {
                players.current[i] = el;
              }}
              controls
              preload="metadata"
              src={slide.src}
              className={VIDEO_FRAME}
            />
            <figcaption>
              <SlideCaption slide={slide} />
            </figcaption>
          </figure>
        ))}
      </div>
      {several && (
        <CarouselDots
          labels={slides.map((s) => `Rede von ${s.speaker}`)}
          active={active}
          onSelect={goTo}
        />
      )}
    </div>
  );
}

/**
 * The section's speeches on video: one per Fraktion, in the same order as the
 * party positions above, while the speaker names there link to the protocol.
 */
export function SpeechMedia({ section }: { section: DigestSessionSection }) {
  const representatives = representativeSlides(section);
  const slides =
    representatives.length > 0
      ? representatives
      : citationSlides(section.citations);

  if (slides.length > 0) {
    return <VideoCarousel slides={slides} />;
  }
  return section.video_url ? (
    <video
      controls
      preload="metadata"
      src={`${section.video_url.split('#')[0]}#t=0.5`}
      className={cn('mt-1', VIDEO_FRAME)}
    />
  ) : null;
}
