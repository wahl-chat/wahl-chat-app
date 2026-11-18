'use client';

import DeleteOpinionsDialog from '@/components/delete-opinions-dialog';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

/** Withdrawal where the privacy policy describes it, so it is reachable from
 * every page that links there, not only from the feed's menu. */
export function DeleteOpinionsButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        Meine Bewertungen löschen
      </Button>
      <DeleteOpinionsDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
