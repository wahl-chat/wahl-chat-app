import { useAnonymousAuth } from '@/components/anonymous-auth';
import { Button } from '@/components/ui/button';
import { userAllowNewsletter } from '@/lib/firebase/firebase';
import { track } from '@vercel/analytics/react';
import { HeartHandshakeIcon, XIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';

type Props = {
  onSuccess: () => void;
};

function SuccessAuthForm({ onSuccess }: Props) {
  const t = useTranslations('auth.newsletter');
  const { user } = useAnonymousAuth();

  const handleSubscribe = async () => {
    track('newsletter_subscribe');
    if (user) {
      await userAllowNewsletter(user.uid, true);
    }

    onSuccess();
  };

  const handleUnsubscribe = async () => {
    track('newsletter_unsubscribe');

    if (user) {
      await userAllowNewsletter(user.uid, false);
    }

    onSuccess();
  };

  return (
    <div className="flex flex-col items-center justify-center gap-4 p-4">
      <div className="flex flex-col items-center justify-center gap-2">
        <h1 className="text-2xl font-bold">{t('title')}</h1>
        <p className="text-center text-sm text-muted-foreground">
          {t('description')}
        </p>
      </div>
      <div className="grid w-full grid-cols-2 gap-2">
        <Button onClick={handleSubscribe}>
          <HeartHandshakeIcon />
          {t('yes')}
        </Button>
        <Button variant="outline" onClick={handleUnsubscribe}>
          <XIcon />
          {t('no')}
        </Button>
      </div>
    </div>
  );
}

export default SuccessAuthForm;
