'use client';

import { createContext, useContext } from 'react';

/** Opens another feed item over the open one, so back returns to it. False
 * when the item is not loaded and the link has to load the page. */
export const OpenFeedItemContext = createContext<
  ((key: string) => boolean) | null
>(null);

export function useOpenFeedItem() {
  return useContext(OpenFeedItemContext);
}

/** The item key a feed link points at. */
export function feedItemKeyOf(href: string): string | null {
  return new URL(href, 'https://wahl.chat').searchParams.get('item');
}
