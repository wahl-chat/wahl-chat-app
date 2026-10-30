// Shared recipes of the parliament feed. Everything keys off the .daily-theme
// variables, so light and dark mode share one set of classes.

export const CARD_SURFACE =
  'rounded-xl border border-[var(--daily-border)] bg-[var(--daily-canvas)]';

export const FOCUS_RING =
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--daily-ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--daily-canvas)]';

/** Grey pill: topic filters, suggested questions, Ja/Nein feedback. */
export const PILL =
  'inline-flex min-h-10 shrink-0 items-center gap-2 whitespace-nowrap rounded-full bg-[var(--daily-surface)] px-4 text-[15px] transition-colors hover:bg-[var(--daily-border)]';

export const PILL_ACTIVE =
  'bg-[var(--daily-ink)] text-[var(--daily-canvas)] hover:bg-[var(--daily-ink)]';

/** Small muted meta line: "Plenarsitzung · Protokoll 21/91". */
export const META_TEXT = 'text-[13px] text-[var(--daily-muted)]';

export const MUTED_TEXT = 'text-[var(--daily-muted)]';

/** Section label inside cards and detail pages: "Kurz gesagt". */
export const SECTION_LABEL = 'text-sm font-semibold text-[var(--daily-muted)]';
