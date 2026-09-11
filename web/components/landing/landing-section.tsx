import { cn } from '@/lib/utils';

type Props = {
  id?: string;
  /**
   * The section's single h2. Omitted for sections that carry their own label,
   * such as the press strip's "Bekannt aus:".
   */
  title?: string;
  className?: string;
  /**
   * Narrows the band. Applied to the same element as the heading so the two
   * cannot end up on different left edges.
   */
  contentClassName?: string;
  children: React.ReactNode;
};

/**
 * One band of the landing page.
 *
 * Owns the side gutter, the vertical rhythm and the heading level so the eight
 * sections cannot drift apart, and so the page keeps exactly one h2 per
 * section under its single h1.
 */
function LandingSection({
  id,
  title,
  className,
  contentClassName,
  children,
}: Props) {
  return (
    <section id={id} className={cn('w-full px-5 py-14 md:py-20', className)}>
      <div className={cn('mx-auto w-full max-w-5xl', contentClassName)}>
        {title && (
          <h2 className="mb-8 text-balance text-2xl font-bold tracking-tight text-foreground md:text-3xl">
            {title}
          </h2>
        )}

        {children}
      </div>
    </section>
  );
}

export default LandingSection;
