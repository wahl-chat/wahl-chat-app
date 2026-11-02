import { Link } from '@/i18n/navigation';
import { MailIcon, MessageSquareHeart } from 'lucide-react';
import { useTranslations } from 'next-intl';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './chat/responsive-drawer-dialog';
import { Button } from './ui/button';
type Props = {
  children: React.ReactNode;
};

function FeedbackDialog({ children }: Props) {
  const t = useTranslations('common.feedbackDialog');

  return (
    <ResponsiveDialog>
      <ResponsiveDialogTrigger asChild>{children}</ResponsiveDialogTrigger>

      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{t('title')}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {t('description')}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        <div className="flex w-full flex-col gap-2 p-4 md:p-0">
          <Button asChild variant="outline">
            <Link href="mailto:info@wahl.chat">
              <MailIcon />
              {t('email')}
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link
              href="https://forms.fillout.com/t/cGozfJUor9us"
              target="_blank"
            >
              <MessageSquareHeart />
              {t('form')}
            </Link>
          </Button>
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default FeedbackDialog;
