import { cn } from '@/lib/utils';

type Props = {
  id?: string;
  title: string;
  eyebrow?: string;
  description?: string;
  children: React.ReactNode;
};

/** Shared card geometry keeps the landing page's sections on one visual axis. */
function LandingSection({ id, title, eyebrow, description, children }: Props) {
  return (
    <section id={id} className="w-full px-5 pb-6 md:pb-8">
      <div className="mx-auto w-full max-w-5xl overflow-hidden rounded-3xl border border-border/70 bg-muted/20">
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
      </div>
    </section>
  );
}

export default LandingSection;
