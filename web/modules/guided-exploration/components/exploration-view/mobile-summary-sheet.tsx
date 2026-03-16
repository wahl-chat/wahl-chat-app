'use client';

import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import type {
  LeafSummary,
  TopicTree,
} from '@/modules/guided-exploration/types';
import { ClipboardList } from 'lucide-react';
import { useState } from 'react';
import { ExplorationSummaryPanel } from './exploration-summary-panel';

interface MobileSummarySheetProps {
  tree: TopicTree;
  currentPath: string[];
  summaries: Record<string, LeafSummary> | null;
  onNavigate: (topicId: string, subtopicId: string) => void;
}

/**
 * Mobile wrapper for the summary panel using a Sheet component.
 * Only visible on mobile (below md breakpoint).
 */
export function MobileSummarySheet({
  tree,
  currentPath,
  summaries,
  onNavigate,
}: MobileSummarySheetProps) {
  const [open, setOpen] = useState(false);

  const handleNavigate = (topicId: string, subtopicId: string) => {
    onNavigate(topicId, subtopicId);
    setOpen(false);
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="md:hidden"
          aria-label="Fortschritt anzeigen"
        >
          <ClipboardList className="size-4" />
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-80 p-0">
        <SheetHeader className="sr-only">
          <SheetTitle>Fortschritt</SheetTitle>
          <SheetDescription>
            Übersicht über den Erkundungsfortschritt
          </SheetDescription>
        </SheetHeader>
        <ExplorationSummaryPanel
          tree={tree}
          currentPath={currentPath}
          summaries={summaries}
          onNavigate={handleNavigate}
          className="h-full"
        />
      </SheetContent>
    </Sheet>
  );
}
