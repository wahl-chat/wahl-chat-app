import HowTo from '@/components/how-to';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'So funktioniert wahl.chat',
  description:
    'Erfahre, wie du wahl.chat nutzen kannst – Parteien vergleichen, Fragen stellen und quellengestützte Antworten erhalten.',
  robots: 'noindex',
};

function HowToPage() {
  return (
    <>
      <h1 className="mb-2 mt-4 text-xl font-bold md:text-2xl">
        Was kann ich mit <span className="underline">wahl.chat</span> alles
        machen?
      </h1>
      <HowTo />
    </>
  );
}

export default HowToPage;
