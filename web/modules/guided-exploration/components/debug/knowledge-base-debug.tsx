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
  explorationApi,
} from '@/modules/guided-exploration/services/exploration-api';
import type { ExplorationTree } from '@/modules/guided-exploration/types';
import { Bug, ChevronRight, Loader2 } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

interface KnowledgeBaseDebugProps {
  sessionId: string;
  explorationId: string;
  tree: ExplorationTree;
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
                <div className="font-mono text-xs text-foreground">
                  {data.explorationId}
                </div>

                {tree.root.children.map((node) => (
                  <Collapsible key={node.id} defaultOpen>
                    <CollapsibleTrigger className="-mx-2 flex w-full items-center gap-2 rounded p-2 text-left hover:bg-muted/50">
                      <ChevronRight className="size-4 transition-transform [[data-state=open]>&]:rotate-90" />
                      <span className="font-semibold">{node.name}</span>
                      <span className="ml-auto text-xs text-foreground">
                        {node.children.length} children
                      </span>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="space-y-3 pl-6 pt-2">
                      {node.children.map((child) => (
                        <Collapsible key={child.id}>
                          <CollapsibleTrigger className="-mx-2 flex w-full items-center gap-2 rounded px-2 py-1 text-left hover:bg-muted/50">
                            <ChevronRight className="size-3 transition-transform [[data-state=open]>&]:rotate-90" />
                            <span className="text-sm">{child.name}</span>
                            <span className="ml-auto text-xs text-foreground">
                              {child.positionIds.length} positions
                            </span>
                          </CollapsibleTrigger>
                          <CollapsibleContent className="pb-3 pt-2">
                            <p className="pl-4 text-xs text-foreground">
                              Parties: {child.partyIds.join(', ')}
                            </p>
                          </CollapsibleContent>
                        </Collapsible>
                      ))}
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
