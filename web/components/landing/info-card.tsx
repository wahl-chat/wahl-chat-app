import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';
import cardStyles from './info-card.module.css';

export type GridPosition = 'top-left' | 'top-center' | 'top-right';

type Props = {
  children: ReactNode;
  gridPosition?: GridPosition;
};

function InfoCard({ children, gridPosition = 'top-left' }: Props) {
  return (
    <div
      data-grid-position={gridPosition}
      className={cn(
        cardStyles.card,
        'mx-auto w-full max-w-5xl overflow-hidden rounded-3xl border border-border/70 bg-muted/20',
      )}
    >
      {children}
    </div>
  );
}

export default InfoCard;
