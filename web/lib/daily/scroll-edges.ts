/** Sub-pixel scroll positions on zoomed or high-DPI screens never quite reach
 * the end, so an edge counts as reached within this many pixels. */
const EDGE_TOLERANCE_PX = 1;

const FADE_PX = 32;

export type ScrollEdges = {
  /** There is more to scroll to on the left. */
  start: boolean;
  /** There is more to scroll to on the right. */
  end: boolean;
};

export function scrollEdges(
  scrollLeft: number,
  clientWidth: number,
  scrollWidth: number,
): ScrollEdges {
  return {
    start: scrollLeft > EDGE_TOLERANCE_PX,
    end: scrollLeft + clientWidth < scrollWidth - EDGE_TOLERANCE_PX,
  };
}

/** A mask that fades out each side with more content behind it; none when
 * everything is in view. */
export function edgeFadeMask({ start, end }: ScrollEdges): string | undefined {
  if (!start && !end) {
    return undefined;
  }
  const left = start ? `transparent 0, black ${FADE_PX}px` : 'black 0';
  const right = end
    ? `black calc(100% - ${FADE_PX}px), transparent 100%`
    : 'black 100%';
  return `linear-gradient(to right, ${left}, ${right})`;
}
