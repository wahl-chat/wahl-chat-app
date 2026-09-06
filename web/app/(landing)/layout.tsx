type Props = {
  children: React.ReactNode;
};

/**
 * Chrome-free shell for the landing page.
 *
 * / deliberately does not use the shared header and footer: it is a single
 * full-viewport panel, so the site logo and the links a visitor still needs
 * are part of that panel rather than a bar above and below it.
 */
function LandingLayout({ children }: Props) {
  return <main className="flex w-full flex-col">{children}</main>;
}

export default LandingLayout;
