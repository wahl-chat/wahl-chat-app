'use client';

import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { useLeafActions } from '@/modules/guided-exploration/components';
import { LeafSummaryCard } from '@/modules/guided-exploration/components/shared/leaf-summary-card';
import type {
  ExplorationTree,
  LeafSummary,
} from '@/modules/guided-exploration/types';
import {
  getAllLeaves,
  getOverallProgress,
} from '@/modules/guided-exploration/utils/tree-helpers';
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

  const progress = getOverallProgress(tree);
  const percentage =
    progress.total > 0
      ? Math.round((progress.explored / progress.total) * 100)
      : 0;

  const exploredLeaves = getAllLeaves(tree).filter(
    (leaf) => leaf.status === 'explored',
  );

  const getSummary = (nodeId: string): LeafSummary | null => {
    if (!summaries) return null;
    return summaries[nodeId] ?? null;
  };

  return (
    <aside
      className="flex h-full flex-col"
      aria-label="Aktuelles Thema und Fortschritt"
    >
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

      {/* Progress */}
      <section
        className="shrink-0 border-b p-4"
        aria-labelledby="study-sidebar-progress-label"
      >
        <div className="mb-2 flex items-center justify-between">
          <h3
            id="study-sidebar-progress-label"
            className="text-sm font-semibold"
          >
            Fortschritt
          </h3>
          <span className="text-xs text-muted-foreground">
            {progress.explored} / {progress.total}
          </span>
        </div>
        <Progress
          value={percentage}
          className="h-2"
          aria-label={`Fortschritt: ${progress.explored} von ${progress.total} Themen besprochen`}
        />
      </section>

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
