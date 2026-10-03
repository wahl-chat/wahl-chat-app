import StimmtsGame from '@/components/stimmts/stimmts-game';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: "Stimmt's?",
  description:
    'Das tägliche Rätsel von wahl.chat: Wie haben die Parteien im Bundestag abgestimmt?',
  // Stays out of search results until the game is released.
  robots: 'noindex',
};

function StimmtsPage() {
  return <StimmtsGame />;
}

export default StimmtsPage;
