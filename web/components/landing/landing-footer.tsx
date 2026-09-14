import Logo from '@/components/chat/logo';
import { ThemeModeToggle } from '@/components/chat/theme-mode-toggle';
import HomeSocialMediaIcon from '@/components/icons/home-social-media-icon';
import { getNextUpcomingElection } from '@/lib/elections';
import { getContexts } from '@/lib/firebase/firebase-server';
import { SITE_LINKS, type SiteLink, sourcesLink } from '@/lib/site-links';
import { IS_EMBEDDED } from '@/lib/utils';
import Link from 'next/link';

/**
 * The landing page's footer.
 *
 * Separate from components/footer.tsx, which is a client component with a
 * fixed h-footer built for the chat shell, and whose Quellen link falls back
 * to the bare /sources geo-redirect. Labels and hrefs come from site-links.ts
 * so the two cannot drift.
 *
 * Impressum und Datenschutz sind nicht optional: sie müssen von jeder Seite
 * einen Klick entfernt sein. They live in the Rechtliches column, which is
 * why the hero no longer carries its own link row.
 */
function FooterColumn({
  label,
  links,
}: {
  label: string;
  links: SiteLink[];
}) {
  if (links.length === 0) return null;

  return (
    <nav aria-label={label} className="flex min-w-0 flex-col gap-3">
      {/* A <p>, not a heading: the footer should not add h2s that compete with
          the page's content sections. The labelled nav names it for AT. */}
      <p className="mb-1 text-sm font-medium text-foreground">{label}</p>

      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className="w-fit text-sm leading-relaxed text-muted-foreground transition-colors hover:text-foreground"
          {...(link.external && {
            target: '_blank',
            rel: 'noopener noreferrer',
          })}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}

async function LandingFooter() {
  const contexts = await getContexts();
  const featured = getNextUpcomingElection(contexts) ?? contexts[0];

  const productLinks: SiteLink[] = [
    SITE_LINKS.howTo,
    ...(featured ? [sourcesLink(featured.context_id)] : []),
    ...(featured
      ? [{ href: `/${featured.context_id}`, label: `Zur ${featured.name}` }]
      : []),
  ];

  const aboutLinks: SiteLink[] = [
    SITE_LINKS.aboutUs,
    SITE_LINKS.donate,
    SITE_LINKS.github,
    ...(IS_EMBEDDED ? [] : [SITE_LINKS.press]),
  ];

  return (
    <footer className="relative isolate w-full overflow-hidden border-t border-border/50 bg-muted/20 px-5 pb-6 pt-12 md:pt-16">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-3 left-1/2 -z-10 w-[115%] -translate-x-1/2 select-none opacity-[0.045] dark:opacity-[0.06]"
      >
        <Logo
          variant="large"
          className="h-auto w-full text-foreground [&_path]:fill-current"
        />
      </div>
      <div className="mx-auto w-full max-w-5xl">
        <div className="grid grid-cols-2 gap-x-6 gap-y-8 md:grid-cols-[0.6fr_1.4fr_1fr_1fr] md:gap-10">
          <Link
            href="/"
            aria-label="wahl.chat Startseite"
            className="col-span-2 w-fit self-start rounded-lg md:col-span-1"
          >
            <Logo variant="small" className="size-10" />
          </Link>
          <FooterColumn label="Produkt" links={productLinks} />
          <FooterColumn label="Über uns" links={aboutLinks} />
          <FooterColumn
            label="Rechtliches"
            links={[SITE_LINKS.imprint, SITE_LINKS.privacy]}
          />
        </div>

        <div className="mt-24 flex flex-wrap items-center justify-between gap-4 md:mt-40">
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} wahl.chat
          </p>
          <div className="flex items-center gap-5">
            {!IS_EMBEDDED && (
              <div className="flex items-center gap-3">
                <HomeSocialMediaIcon type="instagram" className="size-4" />
                <HomeSocialMediaIcon type="linkedin" className="size-4" />
                <HomeSocialMediaIcon type="x" className="size-4" />
                <HomeSocialMediaIcon type="email" className="size-4" />
              </div>
            )}
            <ThemeModeToggle align="end" />
          </div>
        </div>
      </div>
    </footer>
  );
}

export default LandingFooter;
