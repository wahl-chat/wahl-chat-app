import Logo from '@/components/chat/logo';
import { ThemeModeToggle } from '@/components/chat/theme-mode-toggle';
import { SITE_LINKS, sourcesLink } from '@/lib/site-links';
import Link from 'next/link';

type Props = {
  contextId?: string;
};

function LandingHeader({ contextId }: Props) {
  const sources = contextId ? sourcesLink(contextId) : undefined;

  return (
    <header className="border-b border-border px-4 py-3 md:px-6">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4">
        <Link href="/" aria-label="wahl.chat Startseite">
          <Logo className="h-9 w-auto" />
        </Link>

        <div className="flex items-center gap-1 sm:gap-3">
          <nav
            aria-label="Hauptnavigation"
            className="hidden items-center gap-1 sm:flex"
          >
            <Link
              href={SITE_LINKS.howTo.href}
              className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
            >
              {SITE_LINKS.howTo.label}
            </Link>
            {sources && (
              <Link
                href={sources.href}
                className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
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
