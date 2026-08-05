import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { ClapperboardIcon } from 'lucide-react';

type Props = {
  numbers: string[];
  index: number;
  onReferenceClick: (number: number) => void;
  getReferenceTooltip?: (number: number) => string | null;
  getReferenceName?: (number: number) => string | null;
  // True when the reference opens as a video (op speech recording) — rendered
  // as a prominent call-to-action pill instead of a bare number.
  getReferenceIsVideo?: (number: number) => boolean;
};

function ChatMessageReference({
  numbers,
  index,
  onReferenceClick,
  getReferenceTooltip,
  getReferenceName,
  getReferenceIsVideo,
}: Props) {
  return (
    <span key={index} className="inline-flex flex-row flex-wrap gap-1">
      {numbers.map((number) => {
        const refNumber = Number.parseInt(number);

        const name = getReferenceName?.(refNumber) ?? `Ref. ${number}`;
        const tooltip = getReferenceTooltip?.(refNumber) ?? name;
        const isVideo = getReferenceIsVideo?.(refNumber) ?? false;

        return (
          <Tooltip key={number}>
            <TooltipTrigger>
              {/* biome-ignore lint/a11y/useKeyWithClickEvents:  */}
              {/* biome-ignore lint/nursery/noStaticElementInteractions: */}
              <span
                className={cn(
                  'inline-flex cursor-pointer items-center justify-center rounded-full bg-muted px-2 py-1 text-xs transition-colors hover:bg-muted/80',
                  'group-data-[has-message-background=true]:bg-zinc-200 dark:group-data-[has-message-background=true]:bg-zinc-800',
                  isVideo &&
                    'gap-1 bg-primary/10 font-medium text-primary hover:bg-primary/20 dark:bg-primary/20 dark:hover:bg-primary/30',
                )}
                onClick={() => onReferenceClick(Number.parseInt(number))}
              >
                {isVideo ? (
                  <>
                    <ClapperboardIcon className="size-3.5 shrink-0" />
                    <span>Video {name}</span>
                  </>
                ) : (
                  name
                )}
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-96 text-ellipsis whitespace-nowrap">
              {tooltip}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </span>
  );
}

export default ChatMessageReference;
