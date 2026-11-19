import { MAX_SCORE } from '@/lib/stimmts/share-image';

/**
 * The challenge a friend sees when they open a shared result: one line above
 * the game, with the shared score as dots. Both come from `shareChallenge`.
 */
function ShareBanner({ score, text }: { score: number; text: string }) {
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
              index < score
                ? 'size-2 rounded-[2px] bg-[var(--daily-yes)]'
                : 'box-border size-2 rounded-[2px] border border-[var(--daily-muted)]'
            }
          />
        ))}
      </span>
      <span>{text}</span>
    </p>
  );
}

export default ShareBanner;
