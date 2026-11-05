import { BorderTrail } from '@/components/ui/border-trail';

// Slow, since it never stops; long, since a card is far larger than the
// chat input whose trail this mirrors.
const LAP_SECONDS = 4;
const TRAIL_PX = 160;

/** A red light circling the Hot Topic card counterclockwise, as strong as the
 * chat input's trail while an answer is generated. The parent must be
 * `relative` and rounded; the trail shows on its border only. */
function HotTopicTrail() {
  return (
    // rounded-[inherit] passes the card's radius on to the trail's mask.
    <div
      className="pointer-events-none absolute inset-0 rounded-[inherit] motion-reduce:hidden"
      aria-hidden
    >
      <BorderTrail
        reverse
        size={TRAIL_PX}
        className="bg-[#E53935]"
        transition={{
          repeat: Number.POSITIVE_INFINITY,
          duration: LAP_SECONDS,
          ease: 'linear',
        }}
        style={{
          boxShadow:
            '0px 0px 120px 60px rgb(229 57 53 / 100%), 0 0 200px 120px rgb(239 68 68 / 100%), 0 0 280px 180px rgb(248 113 113 / 100%)',
        }}
      />
    </div>
  );
}

export default HotTopicTrail;
