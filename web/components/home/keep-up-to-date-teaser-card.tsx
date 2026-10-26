'use client';

import { type FullUser, useAnonymousAuth } from '@/components/anonymous-auth';
import Logo from '@/components/chat/logo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MailCheckIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useMemo } from 'react';
import { toast } from 'sonner';

type Props = {
  initialUser: FullUser | null;
};

function KeepUpToDateTeaserCard({ initialUser }: Props) {
  const t = useTranslations('home.keepUpToDateCard');
  const { user, updateUser } = useAnonymousAuth();

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.target as HTMLFormElement);
    const email = formData.get('email') as string;

    toast.promise(handleAddEmail(email), {
      loading: t('toast.loading'),
      success: t('toast.success'),
      error: t('toast.error'),
      duration: 5000,
    });
  };

  const handleAddEmail = async (email: string) => {
    if (!user) {
      throw new Error('User not found');
    }
    await updateUser({ keep_up_to_date_email: email });
  };

  const normalizedKeepUpToDateEmail = useMemo(() => {
    if (!user?.keep_up_to_date_email) {
      return initialUser?.keep_up_to_date_email ?? null;
    }

    return user.keep_up_to_date_email;
  }, [user, initialUser]);

  if (normalizedKeepUpToDateEmail) {
    return null;
  }

  return (
    <div className="relative mt-4 flex flex-col gap-2 overflow-hidden rounded-md border border-border bg-muted p-4">
      <div className="flex items-center gap-4">
        <Logo variant="small" className="size-6" />
        <div className="flex flex-col">
          <h1 className="text-base font-bold">{t('title')}</h1>
          <p className="text-sm text-muted-foreground">
            {t.rich('subtitle', {
              bold: (chunks) => <span className="font-bold">{chunks}</span>,
            })}
          </p>
        </div>
      </div>

      <p className="text-sm text-muted-foreground">{t('description')}</p>

      <form className="flex flex-col gap-2 md:flex-row" onSubmit={handleSubmit}>
        <Input
          name="email"
          placeholder={t('emailPlaceholder')}
          type="email"
          autoComplete="email"
          autoCapitalize="off"
          spellCheck="false"
          required
        />

        <Button type="submit">
          <MailCheckIcon />
          {t('submit')}
        </Button>
      </form>
    </div>
  );
}

export default KeepUpToDateTeaserCard;
