import { Markdown } from '@/components/markdown';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Impressum',
  description: 'Impressum und Kontaktdaten von wahl.chat.',
  robots: 'noindex',
};

function Impressum() {
  const markdown = `
# Impressum
        
## Adresse
*Robin Frasch*  
An der Verbindungsbahn 7 
20146 Hamburg  
Deutschland

## Kontakt
**E-Mail:** info@wahl.chat
  `;

  return (
    <div className="mx-auto w-full">
      <Markdown onReferenceClick={() => {}}>{markdown}</Markdown>
    </div>
  );
}

export default Impressum;
