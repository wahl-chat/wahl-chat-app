import Logo from '@/components/chat/logo';
import HomeSocialMediaIcon from '@/components/icons/home-social-media-icon';
import { Separator } from '@/components/ui/separator';
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
    <nav aria-label={label} className="flex flex-col gap-2">
      {/* A <p>, not a heading: the footer should not add h2s that compete with
          the page's content sections. The labelled nav names it for AT. */}
      <p className="text-sm font-semibold text-foreground">{label}</p>

      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
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
    <footer className="w-full border-t border-border px-5 py-12 md:py-16">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-4">
            <Logo variant="small" className="size-6" />

            {!IS_EMBEDDED && (
              <div className="flex items-center gap-3">
                <HomeSocialMediaIcon type="instagram" className="size-5" />
                <HomeSocialMediaIcon type="linkedin" className="size-5" />
                <HomeSocialMediaIcon type="x" className="size-5" />
                <HomeSocialMediaIcon type="email" className="size-5" />
              </div>
            )}
          </div>

          <FooterColumn label="Produkt" links={productLinks} />
          <FooterColumn label="Über uns" links={aboutLinks} />
          <FooterColumn
            label="Rechtliches"
            links={[SITE_LINKS.imprint, SITE_LINKS.privacy]}
          />
        </div>

        <Separator />

        <p className="text-xs text-muted-foreground">
          © {new Date().getFullYear()} wahl.chat
        </p>
      </div>
    </footer>
  );
}

export default LandingFooter;
