/**
 * Geometry shared by the two things that pin themselves to the top of the
 * landing page — the mark on the left and the call to action on the right.
 *
 * They have to agree, so the numbers live here rather than in each component:
 * the pinned height is a compromise between the button's natural 56px and the
 * mark's 30px, and was checked by measuring both once pinned.
 */

export const PINNED_TOP = 12;
/** Gutter from the viewport edge, matching the page's own px-5. */
export const PINNED_INSET = 20;
/** The height both settle at. */
export const PINNED_HEIGHT = 48;

/**
 * The call to action's height in the hero, before it slims down.
 *
 * Set on its placeholder in CSS rather than measured and written back, so the
 * measurement stays honest across a resize — see useScrollMorph.
 */
export const HERO_CTA_HEIGHT = 56;
