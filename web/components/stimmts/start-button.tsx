type Props = {
  onStart: () => void;
};

/**
 * "Los geht's": the one pill-shaped button in the game, so it reads as the
 * start. It sits right under the chamber the player is about to fill.
 */
function StartButton({ onStart }: Props) {
  return (
    <button
      type="button"
      onClick={onStart}
      className="group flex h-[60px] w-full items-center justify-between rounded-full bg-primary pl-6 pr-2 font-display text-primary-foreground transition-transform duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.98] motion-reduce:transition-none motion-reduce:active:scale-100"
    >
      <span className="text-[22px] font-extrabold leading-6 tracking-[-0.01em]">
        Los geht’s
      </span>
      <span
        aria-hidden
        className="inline-flex size-11 items-center justify-center rounded-full bg-primary-foreground font-sans text-[22px] font-bold leading-none text-primary transition-transform duration-200 group-hover:translate-x-[3px] motion-reduce:transition-none motion-reduce:group-hover:translate-x-0"
      >
        →
      </span>
    </button>
  );
}

export default StartButton;
