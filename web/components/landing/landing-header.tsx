'use client';

import Logo from '@/components/chat/logo';
import { ThemeModeToggle } from '@/components/chat/theme-mode-toggle';
import { SITE_LINKS, sourcesLink } from '@/lib/site-links';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { useEffect, useState } from 'react';

type Props = {
  contextId?: string;
};

function LandingHeader({ contextId }: Props) {
  const [isCompact, setIsCompact] = useState(false);

  useEffect(() => {
    const updateHeader = () => {
      // Separate thresholds prevent height changes from toggling the header repeatedly.
      setIsCompact((compact) => window.scrollY > (compact ? 8 : 96));
    };
    updateHeader();
    window.addEventListener('scroll', updateHeader, { passive: true });
    return () => window.removeEventListener('scroll', updateHeader);
  }, []);

  const sources = contextId ? sourcesLink(contextId) : undefined;

  return (
    <header
      className={cn(
        'sticky top-0 z-40 border-b px-4 transition-[padding,border-color,background-color,backdrop-filter] duration-300 ease-out motion-reduce:transition-none md:px-6',
        isCompact
          ? 'border-border/30 bg-background/80 py-2 backdrop-blur-xl'
          : 'border-transparent bg-transparent py-6 md:py-8',
      )}
    >
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4">
        <Link
          href="/"
          aria-label="wahl.chat Startseite"
          className="relative block h-10 w-32 shrink-0 sm:w-40"
        >
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 flex items-center"
          >
            <Logo
              variant="large"
              className={cn(
                'h-auto w-32 origin-[57.5%_50%] transition-[opacity,filter,transform] duration-300 ease-out motion-reduce:transition-none sm:w-40',
                isCompact
                  ? 'scale-95 opacity-0 blur-[3px]'
                  : 'scale-100 opacity-100 blur-0',
              )}
            />
          </span>
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 flex items-center"
          >
            <Logo
              variant="small"
              className={cn(
                'size-7 transition-[opacity,filter] [transition-duration:400ms] ease-out motion-reduce:transition-none',
                isCompact ? 'opacity-100 blur-0' : 'opacity-0 blur-[2px]',
              )}
            />
          </span>
        </Link>

        <div className="flex items-center gap-1 sm:gap-3">
          <nav aria-label="Hauptnavigation" className="flex items-center gap-1">
            <Link
              href={SITE_LINKS.howTo.href}
              className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
            >
              {SITE_LINKS.howTo.label}
            </Link>
            {sources && (
              <Link
                href={sources.href}
                className="hidden rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted sm:inline-flex"
              >
                Quellen &amp; Transparenz
              </Link>
            )}
          </nav>
          <ThemeModeToggle align="end" />
        </div>
      </div>
    </header>
  );
}

export default LandingHeader;
