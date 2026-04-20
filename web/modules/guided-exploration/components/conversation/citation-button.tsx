'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { Citation } from '@/modules/guided-exploration/types';

interface CitationButtonProps {
  citation: Citation;
  index: number;
}

/**
 * Inline citation button [1] with tooltip showing source info
 */
export function CitationButton({ citation, index }: CitationButtonProps) {
  const tooltipContent = [
    citation.party,
    citation.document,
    citation.section,
    citation.page && `S. ${citation.page}`,
  ]
    .filter(Boolean)
    .join(' – ');

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center justify-center rounded bg-muted px-1 py-0.5 text-xs font-medium text-foreground transition-colors hover:bg-muted/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label={`Quelle ${index}: ${tooltipContent}`}
        >
          [{index}]
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs">
        <p className="text-sm">{tooltipContent}</p>
      </TooltipContent>
    </Tooltip>
  );
}
