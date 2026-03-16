import { cn } from '@/lib/utils';

type Props = {
  href: string;
  children: React.ReactNode;
  className?: string;
};

function SkipLink({ href, children, className }: Props) {
  return (
    <a
      href={href}
      className={cn(
        'sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-foreground focus:ring-2 focus:ring-ring',
        className,
      )}
    >
      {children}
    </a>
  );
}

export default SkipLink;
