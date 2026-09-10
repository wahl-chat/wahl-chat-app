import Image from 'next/image';

/**
 * Diagonal band of product screenshots drifting behind the hero.
 *
 * Purely decorative: it shows what wahl.chat looks like in use without asking
 * the visitor to read anything, so the screenshots are aria-hidden and carry
 * no alt text. Heavily blurred and dimmed on purpose — at full strength it
 * competes with the headline and the call to action, which are the only two
 * things the hero is actually for.
 */

const SCREENSHOTS = Array.from(
  { length: 14 },
  (_, index) =>
    `/images/rotation/screenshot-${String(index + 1).padStart(2, '0')}.webp`,
);

// Enough cards to span the rotated 150%-wide band at any viewport, built by
// cycling the row's own screenshots. Half a track is what the marquee shifts
// by, so each row renders this twice.
const CARDS_PER_TRACK = 12;

type Row = {
  images: string[];
  /** Seconds for one full pass. Deliberately not shared, so the rows do not
   *  line up into a single visible block sliding past. */
  duration: number;
  reverse?: boolean;
};

// Two rows, not three: the band has to be shorter than the hero or it fills
// the whole panel and the diagonal stops reading as a diagonal.
const ROWS: Row[] = [
  { images: SCREENSHOTS.slice(0, 7), duration: 96 },
  { images: SCREENSHOTS.slice(7), duration: 124, reverse: true },
];

function buildTrack(images: string[]) {
  return Array.from(
    { length: CARDS_PER_TRACK },
    (_, index) => images[index % images.length],
  );
}

function MarqueeRow({ row }: { row: Row }) {
  const track = buildTrack(row.images);

  return (
    <div className="overflow-hidden">
      <div
        className="animate-screenshot-marquee flex w-max gap-3 md:gap-5"
        style={
          {
            '--marquee-duration': `${row.duration}s`,
            animationDirection: row.reverse ? 'reverse' : undefined,
          } as React.CSSProperties
        }
      >
        {/* Rendered twice: the keyframe shifts by half the track, so the second
            copy is what the first one loops back into. */}
        {[0, 1].map((copy) =>
          track.map((src, index) => (
            <div
              key={`${copy}-${index}-${src}`}
              className="h-[180px] w-[106px] shrink-0 overflow-hidden rounded-xl border border-foreground/10 md:h-[230px] md:w-[136px]"
            >
              <Image
                src={src}
                alt=""
                aria-hidden="true"
                width={136}
                height={230}
                sizes="(min-width: 768px) 136px, 106px"
                className="size-full object-cover object-top"
              />
            </div>
          )),
        )}
      </div>
    </div>
  );
}

function ScreenshotWheel() {
  return (
    <div aria-hidden="true" className="absolute inset-0 overflow-hidden">
      <div className="absolute left-1/2 top-1/2 w-[150%] -translate-x-1/2 -translate-y-1/2 rotate-[-8deg] space-y-3 opacity-70 blur-[2px] md:space-y-5">
        {ROWS.map((row) => (
          <MarqueeRow key={row.duration} row={row} />
        ))}
      </div>

      {/* Two scrims rather than one. The flat wash mutes the band evenly, so
          the headline reads the same wherever a bright screenshot happens to
          have drifted; the gradient then fades the band's cut top and bottom
          edges into the page ground. */}
      <div className="absolute inset-0 bg-background/70" />
      <div className="absolute inset-0 bg-gradient-to-b from-background via-background/40 to-background" />
    </div>
  );
}

export default ScreenshotWheel;
