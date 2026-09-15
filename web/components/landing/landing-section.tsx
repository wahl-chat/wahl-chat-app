import { cn } from '@/lib/utils';
import InfoCard, { type GridPosition } from './info-card';

type Props = {
  id?: string;
  title: string;
  eyebrow?: string;
  description?: string;
  gridPosition?: GridPosition;
  children: React.ReactNode;
};

/** Shared card geometry keeps the landing page's sections on one visual axis. */
function LandingSection({
  id,
  title,
  eyebrow,
  description,
  gridPosition = 'top-center',
  children,
}: Props) {
  return (
    <section id={id} className="w-full px-5 pb-6 md:pb-8">
      <InfoCard gridPosition={gridPosition}>
        <div
          className={cn(
            'p-5 sm:p-6',
            description && 'grid gap-4 md:grid-cols-2 md:gap-8',
          )}
        >
          <div>
            {eyebrow && (
              <p className="mb-4 text-xs font-medium uppercase tracking-widest text-muted-foreground">
                {eyebrow}
              </p>
            )}
            <h2 className="text-balance text-3xl font-semibold leading-tight tracking-[-0.035em] md:text-4xl">
              {title}
            </h2>
          </div>
          {description && (
            <p className="self-end text-sm leading-relaxed text-muted-foreground">
              {description}
            </p>
          )}
        </div>
        {children}
      </InfoCard>
    </section>
  );
}

export default LandingSection;
