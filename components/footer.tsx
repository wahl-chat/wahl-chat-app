import { PRESS_LINK } from '@/lib/contact-config';
import Link from 'next/link';
import Logo from './chat/logo';
import { ThemeModeToggle } from './chat/theme-mode-toggle';
import FeedbackDialog from './feedback-dialog';

function Footer() {
  return (
    <footer className="flex h-footer w-full flex-col items-center justify-center gap-4 border-t p-4 text-xs text-muted-foreground md:flex-row">
      <Logo className="size-5" variant="small" />

      <section className="flex grow flex-wrap items-center justify-center gap-2 underline md:justify-end">
        <Link href="/how-to">Anleitung</Link>
        <Link href="/donate">Spenden</Link>
        <Link href="/about-us">Über uns</Link>
        <Link href="/sources">Quellen</Link>
        <Link href={PRESS_LINK} target="_blank">
          Presse
        </Link>
        <FeedbackDialog>
          <button type="button">Feedback</button>
        </FeedbackDialog>
        <Link href="/impressum">Impressum</Link>
        <Link href="/datenschutz">Datenschutz</Link>
      </section>

      <ThemeModeToggle />
    </footer>
  );
}

export default Footer;
