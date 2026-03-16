import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

type Props = {
  numbers: string[];
  index: number;
  onReferenceClick: (number: number) => void;
  getReferenceTooltip?: (number: number) => string | null;
  getReferenceName?: (number: number) => string | null;
};

function ChatMessageReference({
  numbers,
  index,
  onReferenceClick,
  getReferenceTooltip,
  getReferenceName,
}: Props) {
  return (
    <span
      key={index}
      className="inline-flex flex-row flex-wrap gap-1"
      aria-hidden="true"
    >
      {numbers.map((number) => {
        const refNumber = Number.parseInt(number);

        const name = getReferenceName?.(refNumber) ?? `Ref. ${number}`;
        const tooltip = getReferenceTooltip?.(refNumber) ?? name;

        return (
          <Tooltip key={number}>
            <TooltipTrigger asChild>
              <button
                type="button"
                className={cn(
                  'inline-flex cursor-pointer items-center justify-center rounded-full bg-muted px-2 py-1 text-xs transition-colors hover:bg-muted/80',
                  'group-data-[has-message-background=true]:bg-zinc-200 dark:group-data-[has-message-background=true]:bg-zinc-800',
                )}
                onClick={() => onReferenceClick(Number.parseInt(number))}
              >
                {name}
              </button>
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
