'use client';

import type { Context } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { VoteIcon } from 'lucide-react';
import Image from 'next/image';
import { useState } from 'react';

type ContextIconProps = {
  context: Context;
  className?: string;
};

export function ContextIcon({ context, className }: ContextIconProps) {
  const [imageError, setImageError] = useState(false);

  // Try icon_url first, then local fallback based on context_id
  const iconUrl = context.icon_url || `/images/${context.context_id}.webp`;

  if (imageError) {
    return (
      <div
        className={cn(
          'flex size-6 items-center justify-center rounded bg-muted',
          className,
        )}
      >
        <VoteIcon className="size-3.5 text-muted-foreground" />
      </div>
    );
  }

  return (
    <Image
      src={iconUrl}
      alt={context.name}
      className={cn('size-6 rounded object-contain', className)}
      width={24}
      height={24}
      onError={() => setImageError(true)}
    />
  );
}

export default ContextIcon;
