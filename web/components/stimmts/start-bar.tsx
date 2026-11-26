import { ArrowRight } from 'lucide-react';
import PillButton from './pill-button';

type Props = {
  onStart: () => void;
};

/**
 * "Los geht's". On a phone it is pinned to the bottom of the screen, so the
 * way into the game never scrolls away however long the briefing gets; the
 * page makes room for it (`data-stimmts-start-bar` in globals.css, whose
 * height must match the padding and button here). From md up the whole
 * screen fits, and it sits in flow under the card.
 */
function StartBar({ onStart }: Props) {
  return (
    <div
      data-stimmts-start-bar
      className="fixed inset-x-0 bottom-0 z-20 border-t border-[var(--daily-border)] bg-[var(--daily-canvas)] px-4 pb-[max(16px,env(safe-area-inset-bottom))] pt-3 shadow-[0_-12px_20px_-8px_rgba(24,24,27,0.10)] dark:shadow-[0_-12px_20px_-8px_rgba(0,0,0,0.6)] md:static md:mt-1.5 md:border-0 md:bg-transparent md:p-0 md:shadow-none"
    >
      <div className="mx-auto max-w-[608px]">
        <PillButton onClick={onStart} className="h-[52px] w-full text-[17px]">
          Los geht’s
          <ArrowRight aria-hidden strokeWidth={2.25} />
        </PillButton>
      </div>
    </div>
  );
}

export default StartBar;
