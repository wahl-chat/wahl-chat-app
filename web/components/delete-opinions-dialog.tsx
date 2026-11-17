'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { withdrawFeedOpinions } from '@/lib/daily/use-feed-opinions';
import { useState } from 'react';
import { toast } from 'sonner';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from './chat/responsive-drawer-dialog';
import { Button } from './ui/button';

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Withdraws the consent to storing opinions on feed items: every stored
 * opinion is deleted and taken out of the totals. */
function DeleteOpinionsDialog({ open, onOpenChange }: Props) {
  const { refreshUser } = useAnonymousAuth();
  const [deleting, setDeleting] = useState(false);

  const confirm = async () => {
    setDeleting(true);
    try {
      await withdrawFeedOpinions();
      await refreshUser();
      toast.success('Deine Bewertungen wurden gelöscht.');
      onOpenChange(false);
    } catch (error) {
      console.error(error);
      toast.error('Das Löschen hat nicht geklappt. Bitte versuch es erneut.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>
            Meine Bewertungen löschen?
          </ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Wir löschen alle deine Bewertungen von Positionen und Abstimmungen
            und nehmen sie aus den Gesamtergebnissen. Deine Einwilligung ist
            damit widerrufen.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <ResponsiveDialogFooter>
          <div className="flex w-full flex-col gap-2 sm:flex-row">
            <Button
              variant="outline"
              className="w-full"
              onClick={() => onOpenChange(false)}
            >
              Abbrechen
            </Button>
            <Button
              variant="destructive"
              className="w-full"
              disabled={deleting}
              onClick={confirm}
            >
              Löschen
            </Button>
          </div>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default DeleteOpinionsDialog;
