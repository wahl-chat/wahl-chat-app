'use client';

import { ContextIcon } from '@/components/context-icon';
import {
  useContexts,
  useCurrentContext,
} from '@/components/providers/context-provider';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ChevronDownIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';

type ContextSelectorProps = {
  className?: string;
};

export function ContextSelector({ className }: ContextSelectorProps) {
  const currentContext = useCurrentContext();
  const contexts = useContexts();
  const router = useRouter();

  const handleContextChange = (contextId: string) => {
    router.push(`/${contextId}`);
  };

  // Don't show selector if there's only one context
  if (contexts.length <= 1) {
    return (
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <ContextIcon context={currentContext} className="size-5" />
        <span className="max-w-[120px] truncate sm:max-w-none">
          {currentContext.name}
        </span>
      </div>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className={`flex items-center gap-1.5 px-2 ${className}`}
        >
          <ContextIcon context={currentContext} className="size-5" />
          <span className="max-w-[120px] truncate sm:max-w-none">
            {currentContext.name}
          </span>
          <ChevronDownIcon className="size-3" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {contexts.map((ctx) => (
          <DropdownMenuItem
            key={ctx.context_id}
            onClick={() => handleContextChange(ctx.context_id)}
            className="flex items-center gap-2"
          >
            <ContextIcon context={ctx} className="size-5" />
            <span>{ctx.name}</span>
            {ctx.context_id === currentContext.context_id && (
              <span className="ml-auto text-xs text-muted-foreground">✓</span>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function ContextBadge() {
  const currentContext = useCurrentContext();

  return (
    <div className="flex items-center gap-1.5">
      <ContextIcon context={currentContext} className="size-5" />
      <span className="text-xs text-muted-foreground">
        {currentContext.name}
      </span>
    </div>
  );
}

export default ContextSelector;
