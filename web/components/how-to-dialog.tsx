import { useTranslations } from 'next-intl';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './chat/responsive-drawer-dialog';
import HowTo from './how-to';

type Props = {
  children: React.ReactNode;
};

function HowToDialog({ children }: Props) {
  const t = useTranslations('howTo');

  return (
    <ResponsiveDialog>
      <ResponsiveDialogTrigger asChild>{children}</ResponsiveDialogTrigger>
      <ResponsiveDialogContent className="flex max-h-[95dvh] flex-col overflow-hidden">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>
            {t.rich('heading', {
              underline: (chunks) => (
                <span className="underline">{chunks}</span>
              ),
            })}
          </ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {t('dialogDescription')}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        <div className="grow overflow-y-auto px-4 md:px-0">
          <HowTo />
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default HowToDialog;
