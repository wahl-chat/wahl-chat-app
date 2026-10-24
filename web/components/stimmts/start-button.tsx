import { ArrowRight } from 'lucide-react';
import PillButton from './pill-button';

type Props = {
  onStart: () => void;
};

/**
 * "Los geht's", right under the chamber the player is about to fill: the
 * same pill as every other step forward in the game.
 */
function StartButton({ onStart }: Props) {
  return (
    <PillButton onClick={onStart}>
      Los geht’s
      <ArrowRight aria-hidden strokeWidth={2.25} />
    </PillButton>
  );
}

export default StartButton;
