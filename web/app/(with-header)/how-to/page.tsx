import HowTo from '@/components/how-to';
import { getContexts } from '@/lib/firebase/firebase-server';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'So funktioniert wahl.chat',
  description:
    'Erfahre, wie du wahl.chat nutzen kannst – Parteien vergleichen, Fragen stellen und quellengestützte Antworten erhalten.',
};

// This page is not context-specific, so the supported elections are read here and
// handed to HowTo (inside a chat they come from the ContextProvider instead).
export const revalidate = 3600;

async function HowToPage() {
  const contexts = await getContexts();

  return (
    <>
      <h1 className="mb-2 mt-4 text-xl font-bold md:text-2xl">
        Was kann ich mit <span className="underline">wahl.chat</span> alles
        machen?
      </h1>
      <HowTo contexts={contexts} />
    </>
  );
}

export default HowToPage;
