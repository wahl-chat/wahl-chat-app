import Logo from '@/components/chat/logo';
import JsonLd from '@/components/seo/json-ld';
import { SourcesContextBadge } from '@/components/sources/sources-context-badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Link } from '@/i18n/navigation';
import { WAHL_CHAT_PARTY_ID } from '@/lib/constants';
import {
  getContext,
  getPartiesForContext,
  getSourceDocumentsForContext,
} from '@/lib/firebase/firebase-server';
import type { SourceDocument } from '@/lib/firebase/firebase.types';
import {
  buildContextCanonical,
  buildContextJsonLd,
  buildContextMetadata,
  resolveLocale,
} from '@/lib/seo';
import { buildPartyImageUrl } from '@/lib/utils';
import type { Metadata } from 'next';
import { getLocale, getTranslations } from 'next-intl/server';
import Image from 'next/image';

type Props = {
  params: Promise<{
    contextId: string;
  }>;
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; contextId: string }>;
}): Promise<Metadata> {
  const { locale: localeParam, contextId } = await params;
  const locale = resolveLocale(localeParam);
  const t = await getTranslations({ locale, namespace: 'sources.page' });
  const context = await getContext(contextId);

  if (!context) {
    return { title: t('metaTitle') };
  }

  return {
    ...buildContextMetadata(context, {
      pageSuffix: t('metaTitle'),
      path: 'sources',
      locale,
    }),
    ...buildContextCanonical(contextId, 'sources', locale),
  };
}

async function SourcesPage({ params }: Props) {
  const { contextId } = await params;
  const t = await getTranslations('sources.page');
  const locale = resolveLocale(await getLocale());

  const [sources, parties, context] = await Promise.all([
    getSourceDocumentsForContext(contextId),
    getPartiesForContext(contextId),
    getContext(contextId),
  ]);

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
      {context && (
        <JsonLd data={buildContextJsonLd(context, 'sources', locale)} />
      )}

      <div className="mt-4 flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
        <h1 className="text-xl font-bold md:text-2xl">
          {t.rich(context ? 'titleForContext' : 'title', {
            u: (chunks) => <span className="underline">{chunks}</span>,
          })}
        </h1>
        {context && <SourcesContextBadge context={context} />}
      </div>
      <p className="mb-2 mt-4 text-sm text-muted-foreground">{t('intro')}</p>
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
