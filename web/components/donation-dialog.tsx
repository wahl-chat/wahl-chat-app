import { useTranslations } from 'next-intl';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './chat/responsive-drawer-dialog';
import DonationForm from './donation-form';
import VisuallyHidden from './visually-hidden';

type Props = {
  children: React.ReactNode;
};

function DonationDialog({ children }: Props) {
  const t = useTranslations('donate.dialog');

  return (
    <ResponsiveDialog>
      <ResponsiveDialogTrigger asChild>{children}</ResponsiveDialogTrigger>
      <ResponsiveDialogContent>
        <VisuallyHidden>
          <ResponsiveDialogTitle>{t('title')}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {t('description')}
          </ResponsiveDialogDescription>
        </VisuallyHidden>
        <DonationForm />
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default DonationDialog;
