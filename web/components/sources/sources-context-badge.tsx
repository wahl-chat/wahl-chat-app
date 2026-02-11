'use client';

import type { Context } from '@/lib/firebase/firebase.types';
import { VoteIcon } from 'lucide-react';
import Image from 'next/image';
import { useEffect, useState } from 'react';

type Props = {
  context: Context;
};

export function SourcesContextBadge({ context }: Props) {
  const [imageError, setImageError] = useState(false);

  const iconUrl = context.icon_url || `/images/${context.context_id}.webp`;

  // Reset image error when context changes
  useEffect(() => {
    setImageError(false);
  }, [context.context_id, iconUrl]);

  return (
    <div className="flex items-center gap-2 rounded-md border border-border/50 bg-background px-3 py-1.5">
      {imageError ? (
        <VoteIcon className="size-5 shrink-0 text-muted-foreground" />
      ) : (
        <Image
          src={iconUrl}
          alt={context.name}
          className="size-5 shrink-0 rounded object-contain"
          width={20}
          height={20}
          onError={() => setImageError(true)}
        />
      )}
      <span className="text-sm font-medium">{context.name}</span>
    </div>
  );
}
