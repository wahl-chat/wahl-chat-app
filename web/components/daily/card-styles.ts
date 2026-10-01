// Neo-brutalist frames for the /aktuell feed. Everything keys off the
// .daily-theme variables, so light and dark mode share one set of recipes.

export const INK_BORDER = 'border-2 border-[var(--daily-ink)]';

export const CARD_SURFACE = `${INK_BORDER} rounded-md bg-[var(--daily-surface)] shadow-[4px_4px_0_0_var(--daily-ink)]`;

// Lifts on hover and presses flat on click, like a physical key.
export const PRESSABLE =
  'transition-[transform,box-shadow] duration-150 hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[6px_6px_0_0_var(--daily-ink)] active:translate-x-1 active:translate-y-1 active:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--daily-ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--daily-canvas)] motion-reduce:transform-none motion-reduce:transition-none';

export const CARD_INTERACTIVE = `${CARD_SURFACE} ${PRESSABLE} text-left`;

// Tailwind's /40 opacity modifier cannot reach into a hex-valued CSS variable,
// hence color-mix.
export const CARD_PLACEHOLDER =
  'rounded-md border-2 border-dashed border-[color-mix(in_srgb,var(--daily-ink)_40%,transparent)] text-[var(--daily-muted)]';

/** Inverted label strip: ink background, canvas text. */
export const INK_LABEL =
  'inline-flex w-fit items-center gap-1.5 bg-[var(--daily-ink)] px-2 py-0.5 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--daily-canvas)]';

export const MUTED_TEXT = 'text-[var(--daily-muted)]';
