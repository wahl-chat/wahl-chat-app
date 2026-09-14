'use client';

import ChatGroupPartySelect from '@/components/chat/chat-group-party-select';
import ElectionSelect from '@/components/home/election-select';
import HomeInput from '@/components/home/home-input';
import { useLandingComposer } from '@/components/landing/landing-composer-provider';
import LandingHeadline from '@/components/landing/landing-headline';
import { ContextProvider } from '@/components/providers/context-provider';
import { Button } from '@/components/ui/button';
import type {
  Context,
  LlmSystemStatus,
  ProposedQuestion,
} from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import { buildPartyImageUrl } from '@/lib/utils';
import { ChevronDownIcon, PlusIcon } from 'lucide-react';
import Image from 'next/image';
import { useMemo, useState } from 'react';
import glowStyles from './hero-glow.module.css';

type Props = {
  contexts: Context[];
  partiesByContext: Record<string, PartyDetails[]>;
  fallbackQuestions: ProposedQuestion[];
  questionsByContext: Record<string, ProposedQuestion[]>;
  initialSystemStatus: LlmSystemStatus;
  hasValidServerUser?: boolean;
};

function LandingChatHero({
  contexts,
  partiesByContext,
  fallbackQuestions,
  questionsByContext,
  initialSystemStatus,
  hasValidServerUser,
}: Props) {
  const { state, dispatch } = useLandingComposer();
  const selectedContextId = state.contextId;
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
    dispatch({ type: 'context', contextId });
  };

  const headerActions = (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <ElectionSelect onContextChange={handleContextChange} appearance="hero" />
    </div>
  );
  const selectedParties = state.partyIds.map((id) => {
    const party = partiesByContext[selectedContext.context_id]?.find(
      (party) => party.party_id === id,
    );
    return {
      id,
      name: party?.name ?? id,
      backgroundColor: party?.background_color ?? '#e4e4e8',
    };
  });
  const partySelector = (
    <ChatGroupPartySelect
      key={selectedContext.context_id}
      contextId={selectedContext.context_id}
      selectedPartyIdsInStore={state.partyIds}
      onApplySelection={(partyIds) => dispatch({ type: 'parties', partyIds })}
      open={isPartySelectOpen}
      onOpenChange={setIsPartySelectOpen}
    >
      <Button
        id="party-selection"
        variant="ghost"
        className="h-8 gap-1.5 rounded-full border border-border/60 bg-muted/30 px-2.5 py-1 text-left text-xs font-medium text-muted-foreground transition-colors hover:border-border hover:bg-muted/70 hover:text-foreground"
        type="button"
        title={
          selectedParties.length
            ? selectedParties.map((party) => party.name).join(', ')
            : 'Optional: Parteien für deine Frage auswählen'
        }
        aria-label={
          state.partyIds.length
            ? `${state.partyIds.length} ${state.partyIds.length === 1 ? 'Partei' : 'Parteien'} ausgewählt, Auswahl ändern`
            : 'Parteien zum Vergleichen auswählen, optional'
        }
      >
        {selectedParties.length ? (
          <span className="mr-1 flex shrink-0 -space-x-1" aria-hidden="true">
            {selectedParties.slice(0, 3).map((party) => (
              <span
                key={party.id}
                className="relative size-[18px] overflow-hidden rounded-full ring-1 ring-chat-input"
                style={{ backgroundColor: party.backgroundColor }}
              >
                <Image
                  src={buildPartyImageUrl(party.id)}
                  alt=""
                  fill
                  sizes="18px"
                  className="object-contain p-0.5"
                />
              </span>
            ))}
            {selectedParties.length > 3 && (
              <span className="relative flex size-[18px] items-center justify-center rounded-full bg-muted text-[9px] font-medium text-foreground ring-1 ring-chat-input">
                +{selectedParties.length - 3}
              </span>
            )}
          </span>
        ) : (
          <PlusIcon className="size-3.5 shrink-0" aria-hidden="true" />
        )}
        <span>
          {state.partyIds.length
            ? `${state.partyIds.length} ${state.partyIds.length === 1 ? 'Partei' : 'Parteien'}`
            : 'Parteien auswählen'}
        </span>
        <ChevronDownIcon
          className="size-3 shrink-0 opacity-60"
          aria-hidden="true"
        />
      </Button>
    </ChatGroupPartySelect>
  );

  return (
    <ContextProvider
      context={selectedContext}
      contexts={contexts}
      parties={partiesByContext[selectedContext.context_id]}
    >
      <section
        id="frage-stellen"
        className="relative isolate px-4 pb-8 pt-10 sm:px-6 md:pb-12 md:pt-16"
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 -top-28 bottom-0 -z-10 dark:[--glow-center:0.12] dark:[--glow-edge:0.05]"
        >
          <span className={`${glowStyles.layer} ${glowStyles.coral}`} />
          <span className={`${glowStyles.layer} ${glowStyles.purple}`} />
          <span className={`${glowStyles.layer} ${glowStyles.blue}`} />
          <span className={`${glowStyles.layer} ${glowStyles.pink}`} />
        </div>
        <div className="mx-auto flex w-full max-w-3xl flex-col items-center text-center">
          <LandingHeadline isEditing={Boolean(state.question)} />
          <p className="mt-5 max-w-lg text-pretty text-base leading-relaxed text-muted-foreground md:text-lg">
            Was dich bewegt. Was Parteien dazu sagen.
            <br className="hidden sm:block" /> Finde es heraus – im Gespräch,
            mit Quellen.
          </p>

          <HomeInput
            className="mt-8 w-full text-left md:mt-10"
            questions={questions}
            initialSystemStatus={initialSystemStatus}
            hasValidServerUser={hasValidServerUser}
            contextId={selectedContext.context_id}
            appearance="hero"
            value={state.question}
            onValueChange={(question) =>
              dispatch({ type: 'question', question })
            }
            focusRequest={state.focusRequest}
            partyIds={state.partyIds}
            headerActions={headerActions}
            footerActions={partySelector}
          />
        </div>
      </section>
    </ContextProvider>
  );
}

export default LandingChatHero;
