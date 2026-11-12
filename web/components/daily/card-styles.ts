// Shared recipes of the parliament feed. Everything keys off the .daily-theme
// variables, so light and dark mode share one set of classes.

export const CARD_SURFACE =
  'rounded-xl border border-[var(--daily-border)] bg-[var(--daily-canvas)]';

export const FOCUS_RING =
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--daily-ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--daily-canvas)]';

// Hover is a desktop cue only: phones report a tap as a hover that sticks
// until the next tap elsewhere, so every hover effect below is gated on a
// pointer that can actually hover, and the movements on motion being welcome.
// Only the thumbnail (video or hemicycle) and the headline react; the card
// itself stays still. Tailwind only finds whole class names in the source, so
// the variants are spelled out rather than composed.

/** The card is the hover group its thumbnail and headline react to. */
export const CARD_GROUP = 'group relative';

/** The thumbnail zooms inside its frame, which clips it. */
export const MEDIA_POP =
  'transition-transform duration-200 motion-safe:[@media(hover:hover)]:group-hover:scale-[1.04]';

/** The hemicycle grows out of its baseline. */
export const HEMICYCLE_POP =
  'origin-bottom transition-transform duration-200 motion-safe:[@media(hover:hover)]:group-hover:scale-[1.04]';

/** The headline grows a little from its first letter; its colour stays. */
export const HEADLINE_POP =
  'inline-block origin-left transition-transform duration-200 motion-safe:[@media(hover:hover)]:group-hover:scale-[1.02]';

/**
 * The headline's button stretched over the whole card, so a click anywhere
 * opens the detail while the button stays the one tab stop. Its focus ring
 * outlines the card. Controls inside the card sit above it with
 * ABOVE_CARD_LINK.
 */
export const CARD_LINK =
  "text-left after:absolute after:inset-0 after:rounded-xl after:content-[''] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-[var(--daily-ink)]";

export const ABOVE_CARD_LINK = 'relative z-10';

/**
 * "Mehr anzeigen →". Touch screens have no hover to hint that a card opens,
 * so there it is a filled pill; with a mouse, the card's hover does that job
 * and it stays plain text.
 */
export const CARD_ACTION =
  'inline-flex h-9 items-center gap-1.5 rounded-full bg-[var(--daily-action-bg)] px-4 text-[15px] font-semibold text-[var(--daily-ink)] [@media(hover:hover)]:h-8 [@media(hover:hover)]:bg-transparent [@media(hover:hover)]:px-0';

/** Grey pill: topic filters, suggested questions, Ja/Nein feedback. */
export const PILL =
  'inline-flex min-h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-full bg-[var(--daily-surface)] px-4 text-[15px] transition-colors hover:bg-[var(--daily-border)]';

export const PILL_ACTIVE =
  'bg-[var(--daily-ink)] text-[var(--daily-canvas)] hover:bg-[var(--daily-ink)]';

/** Small muted meta line: "Plenarsitzung · Protokoll 21/91". */
export const META_TEXT = 'text-[13px] text-[var(--daily-muted)]';

export const MUTED_TEXT = 'text-[var(--daily-muted)]';

/** Section label inside cards and detail pages: "Kernpunkte". */
export const SECTION_LABEL = 'text-sm font-semibold text-[var(--daily-muted)]';
