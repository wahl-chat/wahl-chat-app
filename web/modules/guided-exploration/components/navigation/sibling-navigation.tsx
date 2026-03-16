import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { SiblingNavigation as SiblingNavigationType } from '@/modules/guided-exploration/types';
import { ArrowLeft, ArrowRight, ArrowUp } from 'lucide-react';

interface SiblingNavigationProps {
  navigation: SiblingNavigationType | null;
  onPrevious: () => void;
  onNext: () => void;
  onBack: () => void;
  className?: string;
}

/**
 * Navigation between sibling subtopics (prev/next) and back to topic
 */
export function SiblingNavigation({
  navigation,
  onPrevious,
  onNext,
  onBack,
  className,
}: SiblingNavigationProps) {
  const hasPrevious = !!navigation?.previous;
  const hasNext = !!navigation?.next;

  return (
    <nav
      className={cn(
        'flex items-center justify-between gap-2 border-t bg-background px-4 py-3',
        className,
      )}
      aria-label="Navigation zwischen Unterthemen"
    >
      {/* Previous button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onPrevious}
        disabled={!hasPrevious}
        className="gap-1"
        aria-label={
          hasPrevious
            ? `Vorheriges Thema: ${navigation?.previous?.name}`
            : 'Kein vorheriges Thema'
        }
      >
        <ArrowLeft className="size-4" />
        <span className="hidden sm:inline">
          {hasPrevious ? navigation?.previous?.name : 'Zurück'}
        </span>
        <span className="sm:hidden">Zurück</span>
      </Button>

      {/* Back to topic button */}
      <Button variant="outline" size="sm" onClick={onBack} className="gap-1">
        <ArrowUp className="size-4" />
        <span className="hidden sm:inline">Zur Übersicht</span>
      </Button>

      {/* Next button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onNext}
        disabled={!hasNext}
        className="gap-1"
        aria-label={
          hasNext
            ? `Nächstes Thema: ${navigation?.next?.name}`
            : 'Kein nächstes Thema'
        }
      >
        <span className="hidden sm:inline">
          {hasNext ? navigation?.next?.name : 'Weiter'}
        </span>
        <span className="sm:hidden">Weiter</span>
        <ArrowRight className="size-4" />
      </Button>
    </nav>
  );
}
