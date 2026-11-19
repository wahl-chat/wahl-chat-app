import { MAX_SCORE } from '@/lib/stimmts/share-image';

/** The shared score ("4/5") in the challenge text, so the dots match it. */
const FRACTION = new RegExp(`(\\d)/${MAX_SCORE}`);

/**
 * The challenge a friend sees when they open a shared result: one line above
 * the game, with the shared score as dots. The text comes from
 * `shareChallenge`; the dots are read back from it so the two cannot differ.
 */
function ShareBanner({ text }: { text: string }) {
  const [before, score = '0', after = ''] = text.split(FRACTION);
  return (
    <p
      role="status"
      className="flex min-h-10 items-center justify-center gap-2 rounded-xl bg-[var(--daily-surface)] px-4 py-2 text-sm leading-5 text-[var(--daily-ink)]"
    >
      <span aria-hidden className="inline-flex gap-0.5">
        {Array.from({ length: MAX_SCORE }, (_, index) => (
          <span
            // The dots never reorder, so the position is the identity.
            // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length row
            key={index}
            className={
              index < Number(score)
                ? 'size-2 rounded-[2px] bg-[var(--daily-yes)]'
                : 'box-border size-2 rounded-[2px] border border-[var(--daily-muted)]'
            }
          />
        ))}
      </span>
      <span>
        {before}
        <b>
          {score}/{MAX_SCORE}
        </b>
        {after}
      </span>
    </p>
  );
}

export default ShareBanner;
