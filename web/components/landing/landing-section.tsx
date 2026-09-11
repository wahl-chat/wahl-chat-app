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
   * Narrows the band. Sits on the same element as the heading, so a narrowed
   * section keeps its heading and its content on one axis.
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
        {/* Left on mobile, centred from md up. Decided here rather than per
            section so every band's heading sits on the same axis: the sections
            differ in how wide their content is, and a left-aligned heading
            then starts at a different x in each one. */}
        {title && (
          <h2 className="mb-8 text-balance text-left text-2xl font-bold tracking-tight text-foreground md:text-center md:text-3xl">
            {title}
          </h2>
        )}

        {children}
      </div>
    </section>
  );
}

export default LandingSection;
