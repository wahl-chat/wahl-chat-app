'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useStudyRunning } from '@/components/providers/study-status-provider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { StateSelection } from '@/lib/daily/region';
import { cn } from '@/lib/utils';
import { track } from '@vercel/analytics/react';
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  SmartphoneIcon,
} from 'lucide-react';
import { useId, useState } from 'react';
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
  // Mobile only: collapsed to its title row so it does not push the feed
  // down. From md up the body is always shown and the toggle is hidden.
  const [expanded, setExpanded] = useState(false);
  const bodyId = useId();
  const body = cn(expanded ? 'flex' : 'hidden', 'md:flex');

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
    // Saffron stays light in both themes, so the text inside is fixed ink.
    <div
      className={cn(
        CARD_SURFACE,
        'relative flex flex-col gap-3 border-[#1A1A1A] bg-[#E9C46A] p-4 text-[#1A1A1A] md:p-5',
      )}
    >
      {/* Title and sign-up share one row; the description runs underneath
          both, which keeps the card (and the social card beside it) low. */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
        <div className="flex min-w-0 items-center gap-4 md:flex-1">
          <span className="flex size-10 shrink-0 -rotate-6 items-center justify-center border-2 border-[#1A1A1A] bg-white shadow-[2px_2px_0_0_#1A1A1A]">
            <SmartphoneIcon className="size-5" />
          </span>
          <h2 className="min-w-0 flex-1 font-display text-xl font-black leading-tight">
            Tägliche Updates aufs Handy
          </h2>
          <button
            type="button"
            aria-expanded={expanded}
            aria-controls={bodyId}
            aria-label={expanded ? 'Weniger anzeigen' : 'Mehr anzeigen'}
            onClick={() => setExpanded((open) => !open)}
            className="flex size-9 shrink-0 items-center justify-center rounded-[4px] border-2 border-[#1A1A1A] bg-white shadow-[2px_2px_0_0_#1A1A1A] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none md:hidden"
          >
            <ChevronDownIcon
              className={cn(
                'size-5 transition-transform motion-reduce:transition-none',
                expanded && 'rotate-180',
              )}
            />
          </button>
        </div>

        {onWaitlist ? (
          <p className={cn(body, 'items-center gap-2 text-sm font-bold')}>
            <CheckCircle2Icon className="size-4" />
            Du stehst auf der Warteliste.
          </p>
        ) : studyRunning !== false ? (
          <p
            className={cn(
              body,
              'w-fit rotate-2 border-2 border-[#1A1A1A] bg-white px-2 py-1 text-xs font-black uppercase tracking-[0.14em]',
            )}
          >
            Bald verfügbar
          </p>
        ) : (
          <form
            onSubmit={handleSubmit}
            className={cn(
              body,
              'flex-col gap-3 md:w-80 md:shrink-0 md:flex-row',
            )}
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
              className="h-11 rounded-[4px] border-2 border-[#1A1A1A] bg-white text-[#1A1A1A] placeholder:text-[#5C5850] focus-visible:ring-[#1A1A1A]"
            />
            <Button
              type="submit"
              disabled={!user}
              className="h-11 rounded-[4px] border-2 border-[#1A1A1A] bg-[#1A1A1A] font-bold text-white shadow-[3px_3px_0_0_#FBF9F4] transition-[transform,box-shadow] hover:-translate-x-px hover:-translate-y-px hover:bg-[#1A1A1A] active:translate-x-[3px] active:translate-y-[3px] active:shadow-none motion-reduce:transform-none"
            >
              Auf die Warteliste
            </Button>
          </form>
        )}
      </div>

      <p id={bodyId} className={cn(body, 'text-sm font-medium')}>
        Bald gibt es einen persönlichen Newsletter: jeden Tag kurz, was in
        deinem Parlament entschieden wurde, zu den Themen, die dich
        interessieren.
      </p>
    </div>
  );
}

export default DailyWaitlistCta;
