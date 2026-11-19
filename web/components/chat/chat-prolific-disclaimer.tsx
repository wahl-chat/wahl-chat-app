'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogClose,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import { useTranslations } from 'next-intl';

type Props = {
  minInteractions: number;
};

function ChatProlificDisclaimer({ minInteractions }: Props) {
  const t = useTranslations('study.prolific');
  const prolificDisclaimerDismissed = useChatStore(
    (state) => state.prolificDisclaimerDismissed,
  );
  const setProlificDisclaimerDismissed = useChatStore(
    (state) => state.setProlificDisclaimerDismissed,
  );

  const open = !prolificDisclaimerDismissed;

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(o) => !o && setProlificDisclaimerDismissed(true)}
    >
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{t('welcomeTitle')}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {t('welcomeDescription')}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <div className="px-4 text-sm md:px-0">
          <p className="mb-4">
            {t.rich('welcomeBody', {
              count: minInteractions,
              strong: (chunks) => <strong>{chunks}</strong>,
            })}
          </p>
          <div className="rounded-md border border-border bg-muted p-4">
            <p className="font-semibold text-foreground">{t('keepTabOpen')}</p>
            <p className="mt-2 text-muted-foreground">{t('codeExplanation')}</p>
          </div>
        </div>

        <ResponsiveDialogFooter>
          <ResponsiveDialogClose asChild>
            <Button className="w-full">{t('start')}</Button>
          </ResponsiveDialogClose>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default ChatProlificDisclaimer;
