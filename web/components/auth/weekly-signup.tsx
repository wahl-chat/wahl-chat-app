'use client';

import Logo from '@/components/chat/logo';
import {
  ResponsiveDialogDescription,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import GithubIcon from '@/components/icons/github-icon';
import GoogleIcon from '@/components/icons/google-icon';
import { Button } from '@/components/ui/button';
import { MailIcon } from 'lucide-react';
import Link from 'next/link';

/** What a "Meine Woche" email will look like. Made up, and marked so. */
function SampleEmail() {
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
              · Mo, 9:00
            </span>
          </div>
          <div className="truncate text-[11px] text-muted-foreground">
            Deine Woche: Krankenkasse, Heizung, Tempolimit
          </div>
        </div>
        <span className="text-[10px] text-muted-foreground">Beispiel</span>
      </div>
      <div className="px-3.5 py-2.5 text-xs leading-snug">
        <p className="mb-1.5">
          Hallo Nathan, das war diese Woche im Bundestag für dich wichtig:
        </p>
        <ol className="flex list-decimal flex-col gap-0.5 pl-[18px] font-semibold">
          <li>Krankenkassenbeiträge: Gesetz beschlossen</li>
          <li>Heizungsgesetz: Die 65-Prozent-Regel fällt</li>
          <li>Tempolimit abgelehnt</li>
        </ol>
        <div className="mt-2 rounded-r-md border-l-[3px] border-[#ED3833] bg-red-500/10 px-2.5 py-2">
          <div className="mb-0.5 text-[11px] font-bold text-red-700 dark:text-red-400">
            Was sich konkret für dich ändert
          </div>
          <div className="truncate text-muted-foreground [mask-image:linear-gradient(90deg,#000_70%,transparent)]">
            Als gesetzlich Versicherter: Deine Zuzahlungen werden angepasst
            um... …
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
  return (
    <div className="flex flex-col gap-4 p-4 md:p-0">
      <SampleEmail />
      <div className="flex flex-col gap-2">
        <ResponsiveDialogTitle className="text-left text-2xl font-extrabold leading-tight tracking-tight">
          Deine Woche im Bundestag
        </ResponsiveDialogTitle>
        <ResponsiveDialogDescription className="text-left text-[15px] text-muted-foreground">
          Jede Woche die wichtigsten Infos aus Debatten und Abstimmungen zu
          deinen Themen.
          <br />
          Bald gehts los, meld dich an und sei dabei!
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
          Mit Google dabei sein
        </Button>
        <div className="relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:border-t after:border-border">
          <span className="relative z-10 bg-background px-2 text-muted-foreground">
            oder
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
            Mit E-Mail
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-11 gap-2"
            onClick={onGithub}
            disabled={disabled}
          >
            <GithubIcon className="!size-4" />
            Mit GitHub
          </Button>
        </div>
      </div>
      <p className="text-center text-xs text-muted-foreground">
        Mit der Anmeldung akzeptierst du unsere{' '}
        <Link href="/datenschutz" target="_blank" className="underline">
          Datenschutzerklärung
        </Link>
        .
      </p>
      <p className="text-center text-sm text-muted-foreground">
        Schon dabei?{' '}
        <Button
          type="button"
          variant="link"
          className="h-auto p-0 font-semibold text-foreground underline-offset-4"
          onClick={onLogin}
          disabled={disabled}
        >
          Anmelden
        </Button>
      </p>
    </div>
  );
}

export default WeeklySignup;
