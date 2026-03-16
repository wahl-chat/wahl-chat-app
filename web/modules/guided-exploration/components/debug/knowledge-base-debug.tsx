'use client';

import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  type KnowledgeBaseResponse,
  type ResolvedKnowledge,
  explorationApi,
} from '@/modules/guided-exploration/services/exploration-api';
import type { TopicTree } from '@/modules/guided-exploration/types';
import { Bug, ChevronRight, Loader2 } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

interface KnowledgeBaseDebugProps {
  sessionId: string;
  explorationId: string;
  tree: TopicTree;
}

function KnowledgeEntry({ knowledge }: { knowledge: ResolvedKnowledge }) {
  return (
    <div className="space-y-3 border-l-2 border-muted pl-4">
      {knowledge.summaryPoints?.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold">Summary Points</p>
          <ul className="list-inside list-disc space-y-1 text-sm">
            {knowledge.summaryPoints.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </div>
      )}

      {knowledge.keyFacts?.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold">Key Facts</p>
          <ul className="list-inside list-disc space-y-1 text-sm">
            {knowledge.keyFacts.map((fact) => (
              <li key={fact}>{fact}</li>
            ))}
          </ul>
        </div>
      )}

      {knowledge.partyPositions &&
        Object.keys(knowledge.partyPositions).length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold">Party Positions</p>
            <div className="space-y-3">
              {Object.entries(knowledge.partyPositions).map(
                ([partyId, pos]) => (
                  <div
                    key={partyId}
                    className="space-y-1 border-l-2 pl-2 text-sm"
                  >
                    <span className="font-medium uppercase">{pos.party}</span>
                    {pos.content && (
                      <div className="whitespace-pre-wrap text-xs text-foreground">
                        {pos.content}
                      </div>
                    )}
                  </div>
                ),
              )}
            </div>
          </div>
        )}

      {knowledge.citationPool?.length > 0 && (
        <div>
          <p className="mb-1 text-xs font-semibold">
            Citations ({knowledge.citationPool.length})
          </p>
          <div className="flex flex-wrap gap-1">
            {knowledge.citationPool.map((citation) => (
              <span
                key={`${citation.party}-${citation.page}`}
                className="rounded bg-muted px-1.5 py-0.5 text-xs uppercase"
              >
                {citation.party} p.{citation.page}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function KnowledgeBaseDebug({
  sessionId,
  explorationId,
  tree,
}: KnowledgeBaseDebugProps) {
  const searchParams = useSearchParams();
  const isDebugMode = searchParams.get('debug') === 'true';

  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [data, setData] = useState<KnowledgeBaseResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchKnowledgeBase = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await explorationApi.getKnowledgeBase(
        sessionId,
        explorationId,
      );
      setData(response);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch knowledge base',
      );
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, explorationId]);

  useEffect(() => {
    if (isOpen && !data && !isLoading) {
      fetchKnowledgeBase();
    }
  }, [isOpen, data, isLoading, fetchKnowledgeBase]);

  if (!isDebugMode) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-4 z-50">
      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetTrigger asChild>
          <Button
            variant="outline"
            size="icon"
            className="size-10 rounded-full bg-background shadow-lg"
          >
            <Bug className="size-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-[600px] sm:max-w-[600px]">
          <SheetHeader>
            <SheetTitle>Knowledge Base Debug</SheetTitle>
          </SheetHeader>
          <ScrollArea className="mt-4 h-[calc(100vh-100px)]">
            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="size-6 animate-spin" />
              </div>
            )}
            {error && (
              <div className="rounded-lg bg-destructive/10 p-4 text-destructive">
                {error}
              </div>
            )}
            {data && (
              <div className="space-y-4 pr-4">
                <div className="font-mono text-xs text-muted-foreground">
                  {data.explorationId}
                </div>

                {tree.topics.map((topic) => (
                  <Collapsible key={topic.id} defaultOpen>
                    <CollapsibleTrigger className="-mx-2 flex w-full items-center gap-2 rounded p-2 text-left hover:bg-muted/50">
                      <ChevronRight className="size-4 transition-transform [[data-state=open]>&]:rotate-90" />
                      <span className="font-semibold">{topic.name}</span>
                      <span className="ml-auto text-xs text-muted-foreground">
                        {topic.subtopics.length} subtopics
                      </span>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="space-y-3 pl-6 pt-2">
                      {topic.subtopics.map((subtopic) => {
                        // Find knowledge by leafId since keys get camelCased
                        const knowledge = data.entries?.subtopics
                          ? Object.values(data.entries.subtopics).find(
                              (k) => k.leafId === subtopic.id,
                            )
                          : undefined;

                        return (
                          <Collapsible key={subtopic.id}>
                            <CollapsibleTrigger className="-mx-2 flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-muted/50">
                              <ChevronRight className="size-3 transition-transform [[data-state=open]>&]:rotate-90" />
                              <span className="text-sm">{subtopic.name}</span>
                              {knowledge ? (
                                <span className="ml-auto text-xs text-green-600">
                                  has data
                                </span>
                              ) : (
                                <span className="ml-auto text-xs text-muted-foreground">
                                  no data
                                </span>
                              )}
                            </CollapsibleTrigger>
                            <CollapsibleContent className="pb-3 pt-2">
                              {knowledge ? (
                                <KnowledgeEntry knowledge={knowledge} />
                              ) : (
                                <p className="pl-4 text-xs text-muted-foreground">
                                  No knowledge base entry for {subtopic.id}
                                </p>
                              )}
                            </CollapsibleContent>
                          </Collapsible>
                        );
                      })}
                    </CollapsibleContent>
                  </Collapsible>
                ))}
              </div>
            )}
          </ScrollArea>
        </SheetContent>
      </Sheet>
    </div>
  );
}
