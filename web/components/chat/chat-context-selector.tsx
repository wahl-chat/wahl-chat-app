'use client';

import { ContextIcon } from '@/components/context-icon';
import {
  useContexts,
  useCurrentContext,
} from '@/components/providers/context-provider';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { formatGermanDate } from '@/lib/utils';
import { CheckIcon, ChevronDownIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useRef, useState } from 'react';

export function ChatContextSelector() {
  const currentContext = useCurrentContext();
  const contexts = useContexts();
  const router = useRouter();
  const [pendingContextId, setPendingContextId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const isNavigatingRef = useRef(false);

  const handleContextSelect = (contextId: string) => {
    if (contextId !== currentContext.context_id) {
      setPendingContextId(contextId);
      setDialogOpen(true);
    }
  };

  const handleConfirmChange = () => {
    // Guard against double-clicks triggering multiple navigations
    if (isNavigatingRef.current || !pendingContextId) return;
    isNavigatingRef.current = true;

    const contextToNavigate = pendingContextId;
    // Close dialog but keep pendingContextId to avoid text flicker during close animation
    setDialogOpen(false);
    // Navigate after dialog close to prevent overlay from getting stuck
    setTimeout(() => {
      router.push(`/${contextToNavigate}`);
    }, 0);
  };

  const handleDialogOpenChange = (open: boolean) => {
    setDialogOpen(open);
    // Only reset state when dialog is fully closed and we're not navigating
    if (!open && !isNavigatingRef.current) {
      setPendingContextId(null);
    }
  };

  const handleCancelChange = () => {
    setDialogOpen(false);
    setPendingContextId(null);
  };

  const pendingContext = pendingContextId
    ? contexts.find((c) => c.context_id === pendingContextId)
    : null;

  const formattedDate = formatGermanDate(currentContext.date, 'medium');

  // Don't show selector if there's only one context
  if (contexts.length <= 1) {
    return (
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <ContextIcon context={currentContext} className="size-5" />
        <span className="max-w-[100px] truncate text-xs sm:max-w-none">
          {currentContext.name}
        </span>
      </div>
    );
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="flex h-12 grow items-center gap-4 px-2 md:!min-w-64"
          >
            <ContextIcon context={currentContext} className="size-5" />
            <div className="flex grow flex-col items-start gap-1">
              <span className="truncate text-xs font-medium leading-none">
                {currentContext.name}
              </span>
              {formattedDate && (
                <span className="text-[10px] leading-none text-muted-foreground">
                  {formattedDate}
                </span>
              )}
            </div>
            <ChevronDownIcon className="size-3" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="start"
          className="w-[var(--radix-popper-anchor-width)] md:w-64"
        >
          {contexts.map((ctx) => {
            const ctxDate = formatGermanDate(ctx.date, 'medium');
            const isSelected = ctx.context_id === currentContext.context_id;

            return (
              <DropdownMenuItem
                key={ctx.context_id}
                onClick={() => handleContextSelect(ctx.context_id)}
                className="flex cursor-pointer items-center gap-2 py-2"
              >
                <ContextIcon context={ctx} className="size-5" />
                <div className="flex flex-1 flex-col">
                  <span className="font-medium">{ctx.name}</span>
                  {ctxDate && (
                    <span className="text-xs text-muted-foreground">
                      {ctxDate}
                      {ctx.location_name && ` · ${ctx.location_name}`}
                    </span>
                  )}
                </div>
                {isSelected && (
                  <CheckIcon className="size-4 shrink-0 text-primary" />
                )}
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={dialogOpen} onOpenChange={handleDialogOpenChange}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Wahl wechseln?</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingContext ? (
                <>
                  Du wechselst zur{' '}
                  <span className="font-medium text-foreground">
                    {pendingContext.name}
                  </span>
                  . Dadurch verlässt du den aktuellen Chat und wirst zur
                  Startseite weitergeleitet.
                </>
              ) : (
                'Dadurch verlässt du den aktuellen Chat und wirst zur Startseite weitergeleitet.'
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={handleCancelChange}>
              Abbrechen
            </AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmChange}>
              Wahl wechseln
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export default ChatContextSelector;
