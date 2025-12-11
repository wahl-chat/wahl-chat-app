import Logo from '@/components/chat/logo';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { WAHL_CHAT_PARTY_ID } from '@/lib/constants';
import { getParties, getSourceDocuments } from '@/lib/firebase/firebase-server';
import type { SourceDocument } from '@/lib/firebase/firebase.types';
import { buildPartyImageUrl } from '@/lib/utils';
import Image from 'next/image';
import Link from 'next/link';

async function SourcesPage() {
  const sources = await getSourceDocuments();
  const parties = await getParties();

  const sourcesByPartyId = sources.reduce(
    (acc, source) => {
      acc[source.party_id] = acc[source.party_id] || [];
      acc[source.party_id].push(source);
      return acc;
    },
    {} as Record<string, SourceDocument[]>,
  );

  return (
    <article>
      <h1 className="mt-4 text-xl font-bold md:text-2xl">
        Quellen die <span className="underline">wahl.chat</span> nutzt
      </h1>
      <p className="mb-2 text-sm text-muted-foreground">
        Diese Quellen nutzt unsere KI für die allgemeinen Antworten. Für das
        Einordnen von Positionen verwenden wir Perplexity.ai, welches sich auf
        aktuelle Informationen aus dem Internet stützt.
      </p>
      <Accordion type="single" collapsible asChild>
        <section>
          {Object.entries(sourcesByPartyId).map(([partyId, sources]) => {
            const party =
              partyId === WAHL_CHAT_PARTY_ID
                ? undefined
                : parties.find((party) => party.party_id === partyId);

            const name = party?.name ?? 'wahl.chat';

            return (
              <AccordionItem value={partyId} key={partyId}>
                <AccordionTrigger>
                  <div className="flex items-center gap-4">
                    {partyId === WAHL_CHAT_PARTY_ID ? (
                      <div className="aspect-square size-8 rounded-full border border-border object-contain p-1">
                        <Logo variant="small" className="size-full" />
                      </div>
                    ) : (
                      <Image
                        src={buildPartyImageUrl(partyId)}
                        alt={name}
                        width={32}
                        height={32}
                        className="aspect-square rounded-full object-contain p-1"
                        style={{ backgroundColor: party?.background_color }}
                      />
                    )}
                    <h2 className="font-bold">{name}</h2>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <ul className="list-inside list-disc">
                    {sources.map((source) => (
                      <li key={source.id}>
                        <Link
                          href={source.storage_url}
                          target="_blank"
                          className="underline"
                        >
                          {source.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </section>
      </Accordion>
    </article>
  );
}

export default SourcesPage;
