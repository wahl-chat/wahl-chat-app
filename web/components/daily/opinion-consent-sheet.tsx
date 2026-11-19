'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { Button } from '@/components/ui/button';
import { Link } from '@/i18n/navigation';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import { cn } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import { useEffect, useRef } from 'react';

/**
 * The opt-in to storing a reader's opinions on feed items, asked on their
 * first tap. How someone would have voted is a political opinion (GDPR
 * Art. 9), so only an explicit „Ja" counts. „Nein" and a dismissed sheet
 * leave no trace at all: nothing is recorded, and the next tap asks again.
 */
export function OpinionConsentSheet({
  open,
  container,
  onAnswer,
}: {
  open: boolean;
  /** The content of the view the sheet opens over, see
   * `ResponsiveDialogContent`. */
  container?: HTMLElement | null;
  onAnswer: (accepted: boolean) => void;
}) {
  const t = useTranslations('opinions.consent');
  // ResponsiveDialog mounts a Drawer and a Dialog on the same handler, so a
  // close event can still arrive after „Ja"; the first answer wins.
  const answered = useRef(false);
  useEffect(() => {
    if (open) {
      answered.current = false;
    }
  }, [open]);
  const answer = (accepted: boolean) => {
    if (answered.current) {
      return;
    }
    answered.current = true;
    onAnswer(accepted);
  };

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(isOpen) => !isOpen && answer(false)}
    >
      <ResponsiveDialogContent
        container={container}
        className={cn(
          DAILY_THEME_CLASSES,
          'border-[var(--daily-border)] bg-[var(--daily-canvas)] text-[var(--daily-ink)] md:max-w-md',
        )}
      >
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{t('title')}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {t('description')}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <div className="space-y-3 px-4 text-sm md:px-0">
          <p>{t('opinion')}</p>
          <p>{t('storage')}</p>
          <p>
            {t.rich('withdraw', {
              link: (chunks) => (
                <Link
                  href="/datenschutz#mFeedBewertungen"
                  target="_blank"
                  className="underline underline-offset-2"
                >
                  {chunks}
                </Link>
              ),
            })}
          </p>
        </div>
        <ResponsiveDialogFooter>
          <div className="flex w-full flex-col gap-2 sm:flex-row">
            <Button
              variant="outline"
              className="w-full"
              onClick={() => answer(false)}
            >
              {t('no')}
            </Button>
            <Button className="w-full" onClick={() => answer(true)}>
              {t('yes')}
            </Button>
          </div>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}
