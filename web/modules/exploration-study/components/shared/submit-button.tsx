'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

export interface SubmitButtonProps {
  isSubmitting?: boolean;
  disabled?: boolean;
  label?: string;
  loadingLabel?: string;
  className?: string;
}

export function SubmitButton({
  isSubmitting = false,
  disabled = false,
  label = 'Weiter',
  loadingLabel = 'Wird gespeichert...',
  className,
}: SubmitButtonProps) {
  return (
    <div className="w-full pt-6">
      <Button
        type="submit"
        disabled={disabled || isSubmitting}
        className={cn('w-full', className)}
      >
        {isSubmitting ? (
          <>
            <Loader2 aria-hidden="true" className="mr-2 size-4 animate-spin" />
            {loadingLabel}
          </>
        ) : (
          label
        )}
      </Button>
    </div>
  );
}
