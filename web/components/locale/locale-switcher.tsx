'use client';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  LOCALES,
  LOCALE_COOKIE,
  LOCALE_INFO,
  type Locale,
} from '@/i18n/locales';
import { usePathname, useRouter } from '@/i18n/navigation';
import { cn } from '@/lib/utils';
import { CheckIcon, ChevronDownIcon } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useSearchParams } from 'next/navigation';
import { useTransition } from 'react';
import { Flag } from './flags';

const ONE_YEAR_S = 60 * 60 * 24 * 365;

/**
 * "🇩🇪 DE ▾": switches the page to another language at the same path,
 * keeping the query, and remembers the choice for prefix-less links.
 */
export function LocaleSwitcher({
  className,
  align = 'end',
}: {
  /** Trigger styling, so it can sit in each header's own look. */
  className?: string;
  align?: 'start' | 'center' | 'end';
}) {
  const locale = useLocale();
  const t = useTranslations('locale');
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();

  const choose = (next: Locale) => {
    if (next === locale) {
      return;
    }
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${ONE_YEAR_S}; samesite=lax`;
    const query = searchParams.toString();
    startTransition(() => {
      router.replace(query ? `${pathname}?${query}` : pathname, {
        locale: next,
      });
    });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={t('current', { language: LOCALE_INFO[locale].endonym })}
        disabled={pending}
        className={cn(
          'flex h-10 items-center gap-2 rounded-lg border border-border px-3 text-[15px] font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60',
          className,
        )}
      >
        <Flag locale={locale} />
        {LOCALE_INFO[locale].short}
        {/* On phones the header is tight; the bordered flag reads as a
            control without it. */}
        <ChevronDownIcon className="hidden size-3.5 sm:block" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align} className="min-w-40">
        {LOCALES.map((option) => (
          <DropdownMenuItem
            key={option}
            lang={option}
            onSelect={() => choose(option)}
            className="flex items-center gap-2.5"
          >
            <Flag locale={option} />
            <span className="flex-1">{LOCALE_INFO[option].endonym}</span>
            {option === locale && <CheckIcon className="size-4" aria-hidden />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
