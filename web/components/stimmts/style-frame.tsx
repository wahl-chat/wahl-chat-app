import { STYLE_THEMES, modeVars, styleVars } from '@/lib/stimmts/style-themes';
import type { StyleId } from '@/lib/stimmts/styles';
import { cn } from '@/lib/utils';
import type { CSSProperties, ReactNode } from 'react';
import StyleDecor from './style-decor';

/**
 * Room above the result for the decoration that sits at the top of the
 * panel (the dome, the light string, the gold corners and laurels).
 */
const PANEL_PADDING: Record<Exclude<StyleId, 'standard'>, string> = {
  papier: 'pt-7 pb-6',
  kuppel: 'pt-[52px] pb-6',
  nacht: 'pt-7 pb-6',
  festlich: 'pt-[58px] pb-6',
  gold: 'pt-[68px] pb-6',
};

function frameStyle(style: StyleId): CSSProperties | undefined {
  if (style === 'standard') {
    return undefined;
  }
  return {
    ...styleVars(style),
    ...modeVars(style),
    background: 'var(--daily-canvas)',
    color: 'var(--daily-ink)',
  } as CSSProperties;
}

/**
 * Papier sets its headlines in the bill sheet's Tinos. The logo opts out with
 * `data-stimmts-brand`: it keeps the game's own face in every style.
 */
const DOCUMENT_HEADLINES =
  '[&_.font-display:not([data-stimmts-brand])]:font-document';

/**
 * The panel a style dresses the result in, reaching out over the column's
 * gutter to the screen's edges. The element stays the same for every style,
 * standard included, so the style arriving after hydration repaints the
 * result instead of remounting it mid-animation; standard adds nothing.
 */
function StyleFrame({
  style,
  children,
}: {
  style: StyleId;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        'relative -mx-4 px-4',
        style !== 'standard' && ['overflow-hidden', PANEL_PADDING[style]],
        style !== 'standard' &&
          STYLE_THEMES[style].displayFont === 'document' &&
          DOCUMENT_HEADLINES,
      )}
      style={frameStyle(style)}
    >
      <StyleDecor style={style} />
      <div className="relative">{children}</div>
    </div>
  );
}

export default StyleFrame;
