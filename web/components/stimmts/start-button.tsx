import { ArrowRight } from 'lucide-react';
import PillButton from './pill-button';

type Props = {
  onStart: () => void;
};

/** "Los geht's", under the chamber the player is about to fill. */
function StartButton({ onStart }: Props) {
  return (
    <PillButton onClick={onStart}>
      Los geht’s
      <ArrowRight aria-hidden strokeWidth={2.25} />
    </PillButton>
  );
}

export default StartButton;
