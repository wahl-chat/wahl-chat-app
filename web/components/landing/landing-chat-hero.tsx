'use client';

import ChatGroupPartySelect from '@/components/chat/chat-group-party-select';
import ElectionSelect from '@/components/home/election-select';
import HomeInput from '@/components/home/home-input';
import AiDisclaimer from '@/components/legal/ai-disclaimer';
import { ContextProvider } from '@/components/providers/context-provider';
import { Button } from '@/components/ui/button';
import type {
  Context,
  LlmSystemStatus,
  ProposedQuestion,
} from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import { ChevronDownIcon, GitCompareIcon } from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';

type Props = {
  contexts: Context[];
  initialContextId: string;
  partiesByContext: Record<string, PartyDetails[]>;
  fallbackQuestions: ProposedQuestion[];
  questionsByContext: Record<string, ProposedQuestion[]>;
  initialSystemStatus: LlmSystemStatus;
  hasValidServerUser?: boolean;
};

function LandingChatHero({
  contexts,
  initialContextId,
  partiesByContext,
  fallbackQuestions,
  questionsByContext,
  initialSystemStatus,
  hasValidServerUser,
}: Props) {
  const [selectedContextId, setSelectedContextId] = useState(initialContextId);
  const [isPartySelectOpen, setIsPartySelectOpen] = useState(false);
  const selectedContext = useMemo(
    () =>
      contexts.find((context) => context.context_id === selectedContextId) ??
      contexts[0],
    [contexts, selectedContextId],
  );

  if (!selectedContext) return null;

  const selectedQuestions = questionsByContext[selectedContext.context_id];
  const questions = selectedQuestions?.length
    ? selectedQuestions
    : fallbackQuestions;

  const handleContextChange = (contextId: string) => {
    setIsPartySelectOpen(false);
    setSelectedContextId(contextId);
  };

  const headerActions = (
    <>
      <Button
        asChild
        variant="secondary"
        size="sm"
        className="h-7 shrink-0 rounded-full px-2 text-xs font-normal"
      >
        <Link href="/how-to">Was kann ich fragen?</Link>
      </Button>
      <Button
        asChild
        variant="secondary"
        size="sm"
        className="h-7 shrink-0 rounded-full px-2 text-xs font-normal"
      >
        <Link href={`/${selectedContext.context_id}/sources`}>
          Wie entstehen die Antworten?
        </Link>
      </Button>
      <Button
        variant="secondary"
        size="sm"
        className="h-7 shrink-0 rounded-full px-2 text-xs font-normal"
        type="button"
        onClick={() => setIsPartySelectOpen(true)}
      >
        Kann ich mehrere Parteien fragen?
      </Button>
    </>
  );
  const partySelector = (
    <ChatGroupPartySelect
      contextId={selectedContext.context_id}
      open={isPartySelectOpen}
      onOpenChange={setIsPartySelectOpen}
    >
      <Button
        id="party-selection"
        variant="secondary"
        className="mt-2 w-full border border-border font-normal"
        type="button"
        aria-label="Parteien zum Vergleichen auswählen, optional"
      >
        <GitCompareIcon aria-hidden="true" />
        <span>Parteien zum Vergleichen auswählen</span>
        <span className="text-xs text-muted-foreground">optional</span>
        <ChevronDownIcon className="ml-auto" aria-hidden="true" />
      </Button>
    </ChatGroupPartySelect>
  );

  return (
    <ContextProvider
      context={selectedContext}
      contexts={contexts}
      parties={partiesByContext[selectedContext.context_id]}
    >
      <section className="px-4 pb-12 pt-9 md:px-6 md:pb-16 md:pt-14">
        <div className="mx-auto flex w-full max-w-3xl flex-col">
          <p className="mb-4 flex items-center gap-2 text-sm font-medium">
            <span
              className="size-1.5 rounded-full bg-muted-foreground"
              aria-hidden="true"
            />
            Weniger suchen. Mehr verstehen.
          </p>

          <h1 className="max-w-3xl text-balance text-4xl font-bold leading-[0.98] tracking-tight sm:text-5xl md:text-6xl">
            Was möchtest du politisch verstehen
            <span className="text-[#ED3833]">?</span>
          </h1>

          <p className="mt-4 max-w-xl text-pretty text-base text-muted-foreground md:text-lg">
            Deine Fragen. Die Wahlprogramme. Ein Gespräch, das Klarheit schafft.
          </p>

          <div className="mt-7">
            <ElectionSelect onContextChange={handleContextChange} />
          </div>

          <HomeInput
            questions={questions}
            initialSystemStatus={initialSystemStatus}
            hasValidServerUser={hasValidServerUser}
            contextId={selectedContext.context_id}
            appearance="hero"
            headerActions={headerActions}
            footerActions={partySelector}
          />

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <p>Einfach losfragen. Keine Parteiauswahl nötig.</p>
            <p className="hidden sm:block">⌘ / Strg + Enter zum Senden</p>
          </div>

          <AiDisclaimer className="text-left" />
        </div>
      </section>
    </ContextProvider>
  );
}

export default LandingChatHero;
