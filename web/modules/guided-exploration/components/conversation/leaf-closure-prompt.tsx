'use client';

import { Button } from '@/components/ui/button';
import { ArrowRight, Check } from 'lucide-react';

interface LeafClosurePromptProps {
  onClose: () => void;
  onContinue: () => void;
  closeDisabled?: boolean;
  continueDisabled?: boolean;
}

/**
 * Replaces the leaf composer once the LLM judges the leaf substantially
 * explored. Two actions: finish the topic or keep digging. Wrapped in a
 * landmark with an explicit heading so screen readers announce the prompt
 * when focus enters the region.
 */
export function LeafClosurePrompt({
  onClose,
  onContinue,
  closeDisabled = false,
  continueDisabled = false,
}: LeafClosurePromptProps) {
  return (
    <section
      aria-labelledby="leaf-closure-heading"
      className="rounded-[24px] border border-primary/20 bg-primary/5 px-4 py-3"
    >
      <h2 id="leaf-closure-heading" className="text-sm font-medium">
        Ich denke, wir haben das Wesentliche zu diesem Thema besprochen.
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Möchtest du das Thema abschließen oder noch weiter erkunden?
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          type="button"
          size="sm"
          onClick={onClose}
          disabled={closeDisabled}
          className="gap-1.5"
        >
          <Check aria-hidden="true" className="size-3.5" />
          Thema abschließen
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={onContinue}
          disabled={continueDisabled}
          className="gap-1.5"
        >
          <ArrowRight aria-hidden="true" className="size-3.5" />
          Weiter erkunden
        </Button>
      </div>
    </section>
  );
}
