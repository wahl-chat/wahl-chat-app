import {
  ResponsiveDialog,
  ResponsiveDialogClose,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from '@/components/chat/responsive-drawer-dialog';
import { STIMMTS_FONT_CLASSES } from '@/lib/stimmts/fonts';
import { cn } from '@/lib/utils';
import { CircleHelp } from 'lucide-react';
import { useEffect, useState } from 'react';
import PillButton from './pill-button';

const SEEN_KEY = 'stimmts:intro-seen';

const STEPS = [
  'Jeden Tag eine echte namentliche Abstimmung des aktuellen Bundestags (seit 2025). Sie kann auch schon ein paar Monate zurückliegen.',
  'Tippe für jede Fraktion: Ja, Nein oder Enthaltung, so wie die Mehrheit der Fraktion abgestimmt hat.',
  'Dann siehst du, wie wirklich abgestimmt wurde und wie viele deiner Tipps stimmen.',
  'Um Mitternacht kommt das nächste Rätsel. 30 Tage sind eine Wahlperiode.',
];

// Only a convenience: without storage the intro simply shows again.
function wasSeen(): boolean {
  try {
    return window.localStorage.getItem(SEEN_KEY) === '1';
  } catch {
    return false;
  }
}

function markSeen() {
  try {
    window.localStorage.setItem(SEEN_KEY, '1');
  } catch {
    // Nothing to remember it in.
  }
}

type Props = {
  /** Opens by itself for a player who has not seen it yet. */
  autoOpen: boolean;
};

/**
 * The rules, under "Los geht's": shown once to a new player, and there to
 * reopen. It says up front that the votes can be months old, so an older
 * puzzle does not read as stale news.
 */
function HowToPlay({ autoOpen }: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (autoOpen && !wasSeen()) {
      setOpen(true);
    }
  }, [autoOpen]);

  const onOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) {
      markSeen();
    }
  };

  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      <ResponsiveDialogTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-1.5 self-center text-sm text-muted-foreground underline-offset-[3px] hover:underline"
        >
          <CircleHelp aria-hidden className="size-4" />
          So funktioniert’s
        </button>
      </ResponsiveDialogTrigger>
      <ResponsiveDialogContent className={cn(STIMMTS_FONT_CLASSES, 'pb-6')}>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle className="font-display text-2xl font-extrabold tracking-[-0.02em]">
            So funktioniert’s
          </ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Wie haben die Parteien im Bundestag abgestimmt?
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <ol className="flex flex-col gap-4 px-4 md:px-0">
          {STEPS.map((step, index) => (
            <li key={step} className="flex gap-3">
              <span className="font-display text-xl font-extrabold tabular-nums leading-6">
                {index + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
        <ResponsiveDialogClose asChild>
          <PillButton className="mt-2 justify-self-center">
            Verstanden
          </PillButton>
        </ResponsiveDialogClose>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default HowToPlay;
