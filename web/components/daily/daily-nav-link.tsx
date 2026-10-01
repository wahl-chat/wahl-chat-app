'use client';

import { cn } from '@/lib/utils';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

type Props = {
  href: string;
  children: React.ReactNode;
};

/** Header tab in the feed's ink-and-paper style: inverted while active. */
function DailyNavLink({ href, children }: Props) {
  const pathname = usePathname();
  const active = href === '/' ? pathname === '/' : pathname.startsWith(href);

  return (
    <Link
      href={href}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'rounded-[4px] border-2 px-3 py-1.5 text-xs font-bold uppercase tracking-[0.14em] transition-colors',
        active
          ? 'border-[var(--daily-ink)] bg-[var(--daily-ink)] text-[var(--daily-canvas)]'
          : 'border-transparent hover:border-[var(--daily-ink)]',
      )}
    >
      {children}
    </Link>
  );
}

export default DailyNavLink;
