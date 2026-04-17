'use client';

import { cn } from '@/lib/utils';
import { CheckCircle2 } from 'lucide-react';
import type { ReactNode } from 'react';

export interface FormItemCardProps {
  /**
   * Whether the form item inside this card has been answered. Drives the
   * tinted background + visible check marker so participants can see at a
   * glance which rows they've already filled in.
   */
  answered: boolean;
  children: ReactNode;
  className?: string;
  /**
   * Optional semantic tag — defaults to a <div>. Pass 'fieldset' to wrap a
   * radiogroup (so the form item's own <legend> is valid).
   */
  as?: 'div' | 'fieldset';
}

export function FormItemCard({
  answered,
  children,
  className,
  as = 'div',
}: FormItemCardProps) {
  const Tag = as;
  return (
    <Tag
      data-answered={answered || undefined}
      className={cn(
        'relative rounded-lg border p-4 transition-colors',
        answered ? 'border-primary/40 bg-primary/5' : 'border-border bg-card',
        className,
      )}
    >
      {answered && (
        <CheckCircle2
          className="absolute right-3 top-3 size-4 text-primary"
          aria-hidden="true"
        />
      )}
      {children}
    </Tag>
  );
}
