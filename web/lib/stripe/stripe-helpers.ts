import { DEFAULT_LOCALE, LOCALE_INFO, type Locale } from '@/i18n/locales';
import { CURRENCY } from './stripe-config';

/** A whole-euro amount with its currency sign where the reader's language puts
 * it: `5 €` in German, `€5` in English. */
export function formatAmountForDisplay(
  amount: number,
  locale: Locale = DEFAULT_LOCALE,
): string {
  const numberFormat = new Intl.NumberFormat(LOCALE_INFO[locale].intl, {
    style: 'currency',
    currency: CURRENCY,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  return numberFormat.format(amount);
}

export function formatAmountForStripe(
  amount: number,
  currency: string,
): number {
  const numberFormat = new Intl.NumberFormat(['de-DE'], {
    style: 'currency',
    currency: currency,
    currencyDisplay: 'symbol',
  });
  const parts = numberFormat.formatToParts(amount);
  let zeroDecimalCurrency = true;
  for (const part of parts) {
    if (part.type === 'decimal') {
      zeroDecimalCurrency = false;
    }
  }
  return zeroDecimalCurrency ? amount : Math.round(amount * 100);
}
