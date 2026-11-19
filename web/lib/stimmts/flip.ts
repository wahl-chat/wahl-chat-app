export type DOMRectLike = {
  x: number;
  y: number;
  width: number;
  height: number;
};

/**
 * The transform that lays `from` onto `to` (FLIP: first, last, invert, play),
 * for an element scaled about its centre: the translation moves its centre
 * onto the target's, and the scale matches the widths. The card is far wider
 * than tall, so matching widths shrinks it to a sliver inside the icon.
 */
export function flipTransform(
  from: DOMRectLike,
  to: DOMRectLike,
): { x: number; y: number; scale: number } {
  return {
    x: to.x + to.width / 2 - (from.x + from.width / 2),
    y: to.y + to.height / 2 - (from.y + from.height / 2),
    scale: from.width > 0 ? to.width / from.width : 1,
  };
}
