import { Button } from '@/components/ui/button';
import {
  type ShareOutcome,
  browserShareEnv,
  fetchShareImage,
  shareText,
} from '@/lib/stimmts/share-action';
import { Share } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const COPIED_MESSAGE_MS = 2500;

type Props = {
  text: string;
  /** The square share image (see the /stimmts/share route). */
  imagePath: string;
  imageName: string;
};

/**
 * "Ergebnis teilen": on phones the share sheet gets the text and the image
 * together; elsewhere the text is copied and the image can be saved.
 */
function ShareButton({ text, imagePath, imageName }: Props) {
  const [outcome, setOutcome] = useState<ShareOutcome | null>(null);
  const [canShare, setCanShare] = useState(false);
  const image = useRef<File | null>(null);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  useEffect(() => () => clearTimeout(resetTimer.current), []);

  // Fetched ahead of the tap: a share sheet only opens straight from a tap,
  // and waiting for the image first would use the tap up.
  useEffect(() => {
    setCanShare('share' in navigator);
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
      {/* Sized to its label, not the column, and a pill like "Los geht's":
          the game opens and closes on the same shape. */}
      <Button
        onClick={handleClick}
        className="h-12 gap-2.5 rounded-full px-6 font-display text-lg font-bold tracking-[-0.01em] shadow-sm transition-transform active:scale-[0.97] motion-reduce:active:scale-100 [&_svg]:size-5"
      >
        {outcome === 'copied' ? (
          'Kopiert ✓'
        ) : (
          <>
            <Share aria-hidden strokeWidth={2.25} />
            {canShare ? 'Ergebnis teilen' : 'Ergebnis kopieren'}
          </>
        )}
      </Button>
      {!canShare && (
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
