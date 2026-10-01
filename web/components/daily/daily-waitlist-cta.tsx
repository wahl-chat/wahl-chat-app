'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useStudyRunning } from '@/components/providers/study-status-provider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { StateSelection } from '@/lib/daily/region';
import { cn } from '@/lib/utils';
import { track } from '@vercel/analytics/react';
import { CheckCircle2Icon, SmartphoneIcon } from 'lucide-react';
import { toast } from 'sonner';
import { CARD_SURFACE } from './card-styles';

type Props = {
  state: StateSelection;
};

function DailyWaitlistCta({ state }: Props) {
  const { user, updateUser } = useAnonymousAuth();
  // While the PledgeTracker study runs, its questionnaire is the only thing
  // the app asks anyone for; `undefined` (not known yet) counts as running.
  const studyRunning = useStudyRunning();
  const onWaitlist = Boolean(user?.daily_digest_waitlist?.email);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const email = String(
      new FormData(event.currentTarget).get('email') ?? '',
    ).trim();
    if (!email) {
      return;
    }
    track('daily_digest_waitlist_joined', { region: state });
    toast.promise(
      updateUser({
        daily_digest_waitlist: {
          email,
          region: state,
          joined_at: new Date(),
        },
      }),
      {
        loading: 'Einen Moment …',
        success: 'Du stehst auf der Warteliste. Wir melden uns!',
        error: 'Das hat nicht geklappt. Bitte versuche es später erneut.',
      },
    );
  };

  return (
    <div
      className={cn(
        CARD_SURFACE,
        'flex flex-col gap-3 p-4 md:flex-row md:items-center md:gap-6',
      )}
    >
      <div className="flex items-start gap-3 md:flex-1">
        <SmartphoneIcon className="mt-0.5 size-5 shrink-0" />
        <div className="flex flex-col gap-0.5">
          <h2 className="font-bold">Tägliche Updates aufs Handy</h2>
          <p className="text-sm text-muted-foreground">
            Bald gibt es einen persönlichen Newsletter: jeden Tag kurz, was in
            deinem Parlament entschieden wurde, zu den Themen, die dich
            interessieren.
          </p>
        </div>
      </div>

      {onWaitlist ? (
        <p className="flex items-center gap-2 text-sm font-medium">
          <CheckCircle2Icon className="size-4 text-green-600" />
          Du stehst auf der Warteliste.
        </p>
      ) : studyRunning !== false ? (
        <p className="text-sm font-medium text-muted-foreground">
          Bald verfügbar.
        </p>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-2 md:w-96 md:flex-row"
        >
          <Input
            name="email"
            type="email"
            placeholder="Deine E-Mail"
            autoComplete="email"
            autoCapitalize="off"
            spellCheck="false"
            aria-label="E-Mail-Adresse für die Warteliste"
            required
          />
          <Button type="submit" disabled={!user}>
            Auf die Warteliste
          </Button>
        </form>
      )}
    </div>
  );
}

export default DailyWaitlistCta;
