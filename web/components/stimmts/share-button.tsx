import type { ShareMethod } from '@/lib/stimmts/analytics';
import {
  type ShareOutcome,
  browserShareEnv,
  fetchShareImage,
  shareText,
} from '@/lib/stimmts/share-action';
import { cn } from '@/lib/utils';
import { Share } from 'lucide-react';
import { type ReactNode, useEffect, useRef, useState } from 'react';
import PillButton from './pill-button';

const COPIED_MESSAGE_MS = 2500;

type Props = {
  text: string;
  /** The square share image (see the /stimmts/share route), if any. */
  image?: { path: string; name: string };
  onShared?: (method: ShareMethod) => void;
  /** Without the icon and with tighter padding, to sit beside another pill. */
  textOnly?: boolean;
  /**
   * Sits beside the pill in one centered row. The save link and the failure
   * text go below the whole row, so they never push the buttons apart.
   */
  actions?: ReactNode;
};

/**
 * "Ergebnis teilen": on phones the share sheet gets the text and the image
 * together; elsewhere the text is copied and the image can be saved.
 */
function ShareButton({
  text,
  image: shareImage,
  onShared,
  textOnly = false,
  actions,
}: Props) {
  const [outcome, setOutcome] = useState<ShareOutcome | null>(null);
  // Unknown until mounted: guessing either way would flash the save link on
  // the other kind of device. The label stays "teilen" on both: copying the
  // text and the link is how a desktop shares.
  const [canShare, setCanShare] = useState<boolean | null>(null);
  const image = useRef<File | null>(null);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  useEffect(() => () => clearTimeout(resetTimer.current), []);

  // Fetched ahead of the tap: a share sheet only opens straight from a tap,
  // and waiting for the image first would use the tap up.
  const imagePath = shareImage?.path;
  const imageName = shareImage?.name;
  useEffect(() => {
    setCanShare('share' in navigator);
    // A file for the previous path must not go out while the new one is
    // still being rendered.
    image.current = null;
    if (!imagePath || !imageName) {
      return;
    }
    let current = true;
    fetchShareImage(imagePath, imageName).then((file) => {
      if (current) {
        image.current = file;
      }
    });
    return () => {
      current = false;
    };
  }, [imagePath, imageName]);

  const handleClick = async () => {
    const result = await shareText(text, browserShareEnv(), image.current);
    setOutcome(result);
    if (result === 'shared' || result === 'copied') {
      onShared?.(result === 'shared' ? 'share' : 'copy');
    }
    clearTimeout(resetTimer.current);
    if (result === 'copied') {
      resetTimer.current = setTimeout(
        () => setOutcome(null),
        COPIED_MESSAGE_MS,
      );
    }
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="flex flex-wrap items-center justify-center gap-2.5">
        <PillButton
          onClick={handleClick}
          className={cn(
            // 44px tall and about 150px wide at 16px text: beside "Stil
            // ändern" the pair fits one row at 375px.
            textOnly && 'h-11 px-[18px] text-base font-semibold',
          )}
        >
          {outcome === 'copied' ? (
            'Kopiert ✓'
          ) : (
            <>
              {!textOnly && <Share aria-hidden strokeWidth={2.25} />}
              Ergebnis teilen
            </>
          )}
        </PillButton>
        {actions}
      </div>
      {/* The button's new label alone is not announced. */}
      <p role="status" className="sr-only">
        {outcome === 'copied' ? 'Ergebnis kopiert' : ''}
      </p>
      {canShare === false && imagePath && (
        <a
          href={imagePath}
          download={imageName}
          className="text-center text-sm text-[var(--daily-muted)] underline underline-offset-[3px]"
        >
          Bild zum Teilen speichern
        </a>
      )}
      {outcome === 'failed' && (
        <>
          <p className="text-sm text-[var(--daily-muted)]">
            Das Kopieren hat nicht geklappt. Markiere den Text und kopiere ihn
            selbst:
          </p>
          <textarea
            readOnly
            value={text}
            rows={4}
            className="w-full rounded-md border border-[var(--daily-border)] bg-[var(--daily-canvas)] p-2 text-sm"
            onFocus={(event) => event.currentTarget.select()}
          />
        </>
      )}
    </div>
  );
}

export default ShareButton;
