import { Button } from '@/components/ui/button';
import {
  type ShareOutcome,
  browserShareEnv,
  shareText,
} from '@/lib/stimmts/share-action';
import { useEffect, useRef, useState } from 'react';

const COPIED_MESSAGE_MS = 2500;

type Props = {
  text: string;
};

function ShareButton({ text }: Props) {
  const [outcome, setOutcome] = useState<ShareOutcome | null>(null);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  useEffect(() => () => clearTimeout(resetTimer.current), []);

  const canShare = typeof navigator !== 'undefined' && 'share' in navigator;

  const handleClick = async () => {
    const result = await shareText(text, browserShareEnv());
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
    <div className="flex flex-col gap-2">
      <Button size="lg" onClick={handleClick}>
        {outcome === 'copied'
          ? 'Kopiert ✓'
          : canShare
            ? 'Ergebnis teilen'
            : 'Ergebnis kopieren'}
      </Button>
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
