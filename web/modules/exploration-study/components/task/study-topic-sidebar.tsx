'use client';

import { Button } from '@/components/ui/button';
import { useLeafActions } from '@/modules/guided-exploration/components';
import { LeafSummaryCard } from '@/modules/guided-exploration/components/shared/leaf-summary-card';
import type {
  ExplorationTree,
  LeafSummary,
} from '@/modules/guided-exploration/types';
import { getAllLeaves } from '@/modules/guided-exploration/utils/tree-helpers';
import { Check } from 'lucide-react';

interface StudyTopicSidebarProps {
  tree: ExplorationTree;
  summaries: Record<string, LeafSummary> | null;
}

/**
 * Study-mode right sidebar.
 *
 * Unlike the default navigable `ExplorationSummaryPanel`, this sidebar is
 * read-only: it orients the participant to the current leaf ("topic"),
 * hosts the "Thema abschließen" button for that leaf, and shows the
 * summary of everything already handled. No click-to-navigate.
 */
export function StudyTopicSidebar({ tree, summaries }: StudyTopicSidebarProps) {
  const { activeLeafNode, closeCurrentLeaf } = useLeafActions();

  const exploredLeaves = getAllLeaves(tree).filter(
    (leaf) => leaf.status === 'explored',
  );

  const getSummary = (nodeId: string): LeafSummary | null => {
    if (!summaries) return null;
    return summaries[nodeId] ?? null;
  };

  return (
    <aside aria-label="Aktuelles Thema" className="flex h-full flex-col">
      {/* Current topic header */}
      <header className="shrink-0 border-b p-4">
        {activeLeafNode ? (
          <>
            <p
              className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
              aria-hidden="true"
            >
              Aktuelles Thema
            </p>
            <h2 className="mt-1 text-base font-semibold leading-tight">
              {activeLeafNode.name}
            </h2>
            {activeLeafNode.description && (
              <p className="mt-2 text-sm text-muted-foreground">
                {activeLeafNode.description}
              </p>
            )}
            <Button
              onClick={closeCurrentLeaf}
              variant="outline"
              size="sm"
              className="mt-3 w-full"
              aria-label="Aktuelles Thema abschließen und zur Übersicht zurück"
              disabled={activeLeafNode.status === 'explored'}
            >
              <Check className="mr-1.5 size-4" aria-hidden="true" />
              Thema abschließen
            </Button>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            Wähle ein Thema aus der Übersicht, um ein Gespräch zu starten.
          </p>
        )}
      </header>

      {/* Already handled */}
      <section
        className="flex-1 overflow-y-auto p-4"
        aria-labelledby="study-sidebar-handled-label"
      >
        <h3
          id="study-sidebar-handled-label"
          className="mb-3 text-sm font-semibold"
        >
          Bereits besprochen
        </h3>
        {exploredLeaves.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Noch nichts besprochen. Stell eine Frage, um loszulegen.
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {exploredLeaves.map((leaf) => (
              <li key={leaf.id}>
                <LeafSummaryCard
                  node={leaf}
                  summary={getSummary(leaf.id)}
                  showPendingHint={false}
                />
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}
