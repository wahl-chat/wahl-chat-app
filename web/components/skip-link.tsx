import { cn } from '@/lib/utils';
import { forwardRef } from 'react';

type Props = {
  href?: string;
  children: React.ReactNode;
  className?: string;
  /**
   * Optional click handler. Use (with `e.preventDefault()`) when the target
   * lives inside a fixed/portalled container, where the browser's default
   * hash-scroll would jump the underlying page instead of moving focus.
   */
  onClick?: React.MouseEventHandler<HTMLAnchorElement>;
};

const SkipLink = forwardRef<HTMLAnchorElement, Props>(
  ({ href, children, className, onClick }, ref) => {
    return (
      <a
        ref={ref}
        href={href}
        onClick={onClick}
        className={cn(
          'sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-foreground focus:ring-2 focus:ring-ring',
          className,
        )}
      >
        {children}
      </a>
    );
  },
);
SkipLink.displayName = 'SkipLink';

export default SkipLink;
