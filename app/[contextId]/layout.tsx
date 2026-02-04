import { ContextProvider } from '@/components/providers/context-provider';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import {
  getContext,
  getContexts,
  getPartiesForContext,
} from '@/lib/firebase/firebase-server';
import { shuffleArray } from '@/lib/utils';
import { notFound, redirect } from 'next/navigation';

export const revalidate = 3600;

type Props = {
  children: React.ReactNode;
  params: Promise<{
    contextId: string;
  }>;
};

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

  // Shuffle parties randomly for fair display order.
  // Note: With ISR (revalidate = 3600), this shuffle is cached for ~1 hour,
  // meaning all users see the same party order during that period.
  const shuffledParties = shuffleArray(parties);

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
