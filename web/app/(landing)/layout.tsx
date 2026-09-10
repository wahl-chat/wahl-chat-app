import LandingFooter from '@/components/landing/landing-footer';

type Props = {
  children: React.ReactNode;
};

/**
 * Shell for the landing page.
 *
 * / deliberately does not use the shared header: the hero fills the viewport
 * and carries the site logo itself, so a bar above it would only compete with
 * the call to action. It does get a footer, outside <main> so it is a real
 * contentinfo landmark — the page is a long scrolling document now, and the
 * links a visitor still needs belong at the end of it rather than crammed
 * under the hero.
 */
function LandingLayout({ children }: Props) {
  return (
    <>
      <main className="flex w-full flex-col">{children}</main>
      <LandingFooter />
    </>
  );
}

export default LandingLayout;
