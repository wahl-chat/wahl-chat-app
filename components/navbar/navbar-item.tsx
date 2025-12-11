'use client';

import { cn } from '@/lib/utils';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export type NavbarItemDetails = {
  label: string;
  href: string;
  highlight?: boolean;
  external?: boolean;
  icon?: React.ReactNode;
};

type Props = {
  details: NavbarItemDetails;
  mobileClose?: () => void;
};

function NavbarItem({ details, mobileClose }: Props) {
  const { label, href, external, highlight } = details;
  const pathname = usePathname();
  const isActive = href === '/' ? pathname === href : pathname.startsWith(href);

  return (
    <Link
      href={href}
      target={external ? '_blank' : undefined}
      className={cn(
        'relative flex items-center p-2 text-sm gap-1 rounded-md',
        isActive
          ? 'text-primary font-medium'
          : 'text-primary/50 hover:text-primary/70',
        highlight &&
          'dark:text-indigo-100 dark:hover:text-indigo-50 border-none text-indigo-900 hover:text-indigo-900',
      )}
      onClick={mobileClose}
    >
      {highlight && (
        <span className="relative mr-1 flex size-2">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-indigo-600 opacity-75" />
          <span className="relative inline-flex size-2 rounded-full bg-indigo-600" />
        </span>
      )}
      <span className="relative z-50">{label}</span>
      {isActive && !highlight && (
        <span className="absolute inset-0 rounded-md bg-muted" />
      )}

      {highlight && (
        <span className="absolute inset-0 rounded-md border border-indigo-600 bg-indigo-600/20 transition-colors hover:bg-indigo-600/30" />
      )}
    </Link>
  );
}

export default NavbarItem;
