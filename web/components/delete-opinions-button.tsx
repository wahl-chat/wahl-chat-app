'use client';

import DeleteOpinionsDialog from '@/components/delete-opinions-dialog';
import { Button } from '@/components/ui/button';
import { useTranslations } from 'next-intl';
import { useState } from 'react';

/** Withdrawal where the privacy policy describes it, so it is reachable from
 * every page that links there, not only from the feed's menu. */
export function DeleteOpinionsButton() {
  const t = useTranslations('opinions.delete');
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        {t('button')}
      </Button>
      <DeleteOpinionsDialog open={open} onOpenChange={setOpen} />
    </>
  );
}
