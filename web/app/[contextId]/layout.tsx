import { ContextProvider } from '@/components/providers/context-provider';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import {
  getContext,
  getContexts,
  getPartiesForContext,
} from '@/lib/firebase/firebase-server';
import { buildContextMetadata } from '@/lib/seo';
import { shuffleArray } from '@/lib/utils';
import type { Metadata } from 'next';
import { notFound, redirect } from 'next/navigation';

// Page is not the photocopy: election config is cached in unstable_cache and
// busted by tag on seed. ISR here would snapshot empty party lists again.
export const dynamic = 'force-dynamic';

type Props = {
  children: React.ReactNode;
  params: Promise<{
    contextId: string;
  }>;
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ contextId: string }>;
}): Promise<Metadata> {
  const { contextId } = await params;
  const context = await getContext(contextId);

  if (!context) {
    // The page body redirects to the default context, so this URL must not be indexed.
    return { robots: 'noindex, nofollow' };
  }

  return buildContextMetadata(context);
}

async function ContextLayout({ children, params }: Props) {
  const { contextId } = await params;

  const [context, contexts, parties] = await Promise.all([
    getContext(contextId),
    getContexts(),
    getPartiesForContext(contextId),
  ]);

  // If context doesn't exist, redirect to default context
  if (!context) {
    // Avoid infinite redirect loop if default context also doesn't exist
    if (contextId === DEFAULT_CONTEXT_ID) {
      notFound();
    }
    redirect(`/${DEFAULT_CONTEXT_ID}`);
  }

  // Shuffle per request for fair display order. The party *list* is cached;
  // the order is not.
  const shuffledParties = shuffleArray(parties);

  // The WebPage node is emitted per page, not here: it carries a URL and an @id,
  // and every route under this layout (/session, /swiper, /share, /sources) would
  // otherwise declare the same node while living at a different URL.
  return (
    <ContextProvider
      context={context}
      contexts={contexts}
      parties={shuffledParties}
    >
      {children}
    </ContextProvider>
  );
}

export default ContextLayout;
