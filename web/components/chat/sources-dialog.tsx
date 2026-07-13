'use client';

import {
  type ActiveMedia,
  SourceMediaViewer,
  SourceRow,
} from '@/components/chat/source-media';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { Source } from '@/lib/stores/chat-store.types';
import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';
import { useState } from 'react';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './responsive-drawer-dialog';

/** A source plus the number shown on its badge (1-based, matches the in-text pill). */
export type NumberedSource = {
  source: Source;
  displayNumber: number;
};

type Props = {
  /** The exact trigger button for this surface (chat vs agent keep their own styling). */
  trigger: ReactNode;
  /** Sources cited in the answer, in citation order. */
  referenced: NumberedSource[];
  /** Sources retrieved but not cited. */
  notReferenced: NumberedSource[];
  /** Optional badge styling override (the agent flow tints its badges). */
  badgeClassName?: string;
};

/**
 * The shared "Quellen" dialog: a trigger button, then either the source list
 * (referenced + additionally-analyzed) or the in-page media viewer for a picked
 * source. Extracted so the chat and agent sources buttons share ONE dialog shell,
 * media-viewer wiring, and German copy instead of duplicating ~70 lines each.
 */
export function SourcesDialog({
  trigger,
  referenced,
  notReferenced,
  badgeClassName,
}: Props) {
  const [activeMedia, setActiveMedia] = useState<ActiveMedia | null>(null);

  const renderRow = (item: NumberedSource, prefix: string) => (
    <SourceRow
      key={`${prefix}-${item.displayNumber}`}
      source={item.source}
      displayNumber={item.displayNumber}
      badgeClassName={badgeClassName}
      onOpenMedia={setActiveMedia}
    />
  );

  return (
    <ResponsiveDialog
      onOpenChange={(open) => {
        if (!open) setActiveMedia(null);
      }}
    >
      <Tooltip>
        <TooltipTrigger asChild>
          <ResponsiveDialogTrigger asChild>{trigger}</ResponsiveDialogTrigger>
        </TooltipTrigger>
        <TooltipContent>Quellen</TooltipContent>
      </Tooltip>
      <ResponsiveDialogContent
        className={cn(
          'flex max-h-[95dvh] flex-col',
          // Widen for document/video viewing so a PDF is legible; keep the list narrow.
          activeMedia && 'md:max-w-3xl',
        )}
      >
        {activeMedia ? (
          <>
            <ResponsiveDialogHeader className="sr-only">
              <ResponsiveDialogTitle>{activeMedia.title}</ResponsiveDialogTitle>
              <ResponsiveDialogDescription>
                Beleg im Fenster ansehen.
              </ResponsiveDialogDescription>
            </ResponsiveDialogHeader>
            <SourceMediaViewer
              media={activeMedia}
              onBack={() => setActiveMedia(null)}
            />
          </>
        ) : (
          <>
            <ResponsiveDialogHeader>
              <ResponsiveDialogTitle>Quellen</ResponsiveDialogTitle>
              <ResponsiveDialogDescription>
                Belege direkt hier ansehen – Reden als Video, Dokumente als PDF.
              </ResponsiveDialogDescription>
            </ResponsiveDialogHeader>

            <div className="flex grow flex-col overflow-y-auto p-4 md:p-0">
              {referenced.length > 0 && (
                <p className="text-sm font-bold">Im Text referenziert:</p>
              )}
              {referenced.map((item) => renderRow(item, 'ref'))}
              {notReferenced.length > 0 && (
                <p
                  className={cn(
                    'text-sm font-bold',
                    referenced.length > 0 && 'mt-4',
                  )}
                >
                  Zusätzlich analysiert:
                </p>
              )}
              {notReferenced.map((item) => renderRow(item, 'notref'))}
            </div>
          </>
        )}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}
