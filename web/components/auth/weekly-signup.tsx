'use client';

import Logo from '@/components/chat/logo';
import {
  ResponsiveDialogDescription,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import GithubIcon from '@/components/icons/github-icon';
import GoogleIcon from '@/components/icons/google-icon';
import { Button } from '@/components/ui/button';
import { Link } from '@/i18n/navigation';
import { MailIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';

/** What a "Meine Woche" email will look like. Made up, and marked so. */
function SampleEmail() {
  const t = useTranslations('auth.weekly.sample');
  return (
    // md:mt-7 keeps the desktop dialog's close button clear of the sample;
    // the phone sheet has none.
    <div
      aria-hidden
      className="overflow-hidden rounded-lg border border-border bg-background text-left md:mt-7"
    >
      <div className="flex items-center gap-2 border-b border-border bg-muted px-3 py-2">
        <span className="flex size-[26px] shrink-0 items-center justify-center rounded-full bg-zinc-900">
          <Logo variant="small" className="size-3.5 text-white" />
        </span>
        <div className="min-w-0 flex-1 leading-tight">
          <div className="text-[11px] font-bold">
            wahl.chat{' '}
            <span className="font-normal text-muted-foreground">
              · {t('sent')}
            </span>
          </div>
          <div className="truncate text-[11px] text-muted-foreground">
            {t('subject')}
          </div>
        </div>
        <span className="text-[10px] font-bold text-muted-foreground">
          {t('badge')}
        </span>
      </div>
      <div className="px-3.5 py-2.5 text-xs leading-snug">
        <p className="mb-1.5">{t('greeting')}</p>
        <ol className="flex list-decimal flex-col gap-0.5 pl-[18px] font-semibold">
          <li>{t('item1')}</li>
          <li>{t('item2')}</li>
          <li>{t('item3')}</li>
        </ol>
        <div className="mt-2 rounded-r-md border-l-[3px] border-[#ED3833] bg-red-500/10 px-2.5 py-2">
          <div className="mb-0.5 text-[11px] font-bold text-red-700 dark:text-red-400">
            {t('changesHeading')}
          </div>
          <div className="truncate text-muted-foreground [mask-image:linear-gradient(90deg,#000_70%,transparent)]">
            {t('changesText')}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * The "Meine Woche" sign-up: a sample of the email, the pitch, and the ways
 * to sign up, Google first. Holds no sign-in logic; the login form passes
 * its own handlers in.
 */
function WeeklySignup({
  onGoogle,
  onGithub,
  onEmail,
  onLogin,
  disabled,
}: {
  onGoogle: () => void;
  onGithub: () => void;
  onEmail: () => void;
  onLogin: () => void;
  disabled: boolean;
}) {
  const t = useTranslations('auth.weekly');
  return (
    <div className="flex flex-col gap-4 p-4 md:p-0">
      <SampleEmail />
      <div className="flex flex-col gap-2">
        <ResponsiveDialogTitle className="text-left text-2xl font-extrabold leading-tight tracking-tight">
          {t('title')}
        </ResponsiveDialogTitle>
        <ResponsiveDialogDescription className="text-left text-[15px] text-muted-foreground">
          {t('pitch')}
          <br />
          {t('soon')}
        </ResponsiveDialogDescription>
      </div>
      <div className="flex flex-col gap-3">
        <Button
          type="button"
          className="h-11 w-full gap-2.5 text-[15px] font-semibold"
          onClick={onGoogle}
          disabled={disabled}
        >
          <span className="flex size-6 items-center justify-center rounded-full bg-white">
            <GoogleIcon className="!size-3.5" />
          </span>
          {t('google')}
        </Button>
        <div className="relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:border-t after:border-border">
          <span className="relative z-10 bg-background px-2 text-muted-foreground">
            {t('or')}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button
            type="button"
            variant="outline"
            className="h-11 gap-2"
            onClick={onEmail}
            disabled={disabled}
          >
            <MailIcon className="size-4" aria-hidden />
            {t('email')}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-11 gap-2"
            onClick={onGithub}
            disabled={disabled}
          >
            <GithubIcon className="!size-4" />
            {t('github')}
          </Button>
        </div>
      </div>
      <p className="text-center text-xs text-muted-foreground">
        {t.rich('consent', {
          link: (chunks) => (
            <Link href="/datenschutz" target="_blank" className="underline">
              {chunks}
            </Link>
          ),
        })}
      </p>
      <p className="text-center text-sm text-muted-foreground">
        {t('already')}{' '}
        <Button
          type="button"
          variant="link"
          className="h-auto p-0 font-semibold text-foreground underline-offset-4"
          onClick={onLogin}
          disabled={disabled}
        >
          {t('login')}
        </Button>
      </p>
    </div>
  );
}

export default WeeklySignup;
