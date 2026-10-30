import type { ShareMethod } from '@/lib/stimmts/analytics';
import {
  type ShareOutcome,
  browserShareEnv,
  fetchShareImage,
  shareText,
} from '@/lib/stimmts/share-action';
import { Share } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import PillButton from './pill-button';

const COPIED_MESSAGE_MS = 2500;

type Props = {
  text: string;
  /** The square share image (see the /stimmts/share route), if any. */
  image?: { path: string; name: string };
  onShared?: (method: ShareMethod) => void;
};

/**
 * "Ergebnis teilen": on phones the share sheet gets the text and the image
 * together; elsewhere the text is copied and the image can be saved.
 */
function ShareButton({ text, image: shareImage, onShared }: Props) {
  const [outcome, setOutcome] = useState<ShareOutcome | null>(null);
  // Unknown until mounted: guessing either way would flash the wrong label
  // (and the save link) on the other kind of device.
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
      <PillButton onClick={handleClick}>
        {outcome === 'copied' ? (
          'Kopiert ✓'
        ) : (
          <>
            <Share aria-hidden strokeWidth={2.25} />
            {canShare === false ? 'Ergebnis kopieren' : 'Ergebnis teilen'}
          </>
        )}
      </PillButton>
      {/* The button's new label alone is not announced. */}
      <p role="status" className="sr-only">
        {outcome === 'copied' ? 'Ergebnis kopiert' : ''}
      </p>
      {canShare === false && imagePath && (
        <a
          href={imagePath}
          download={imageName}
          className="text-center text-sm text-muted-foreground underline underline-offset-[3px]"
        >
          Bild zum Teilen speichern
        </a>
      )}
      {outcome === 'failed' && (
        <>
          <p className="text-sm text-muted-foreground">
            Das Kopieren hat nicht geklappt. Markiere den Text und kopiere ihn
            selbst:
          </p>
          <textarea
            readOnly
            value={text}
            rows={4}
            className="w-full rounded-md border bg-background p-2 text-sm"
            onFocus={(event) => event.currentTarget.select()}
          />
        </>
      )}
    </div>
  );
}

export default ShareButton;
