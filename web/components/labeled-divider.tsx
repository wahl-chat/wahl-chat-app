import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

type Props = {
  children: React.ReactNode;
  className?: string;
};

/**
 * A rule with a small label set into it — "Bekannt aus:", "Zahlen und Fakten:".
 *
 * Extracted so the landing page's two labelled bands share one implementation
 * rather than one copying the other's classes and then drifting from it.
 */
function LabeledDivider({ children, className }: Props) {
  return (
    <div className={cn('flex w-full flex-row items-center gap-4', className)}>
      <Separator className="w-auto grow" />
      <p className="text-xs font-medium text-muted-foreground opacity-50">
        {children}
      </p>
      <Separator className="w-auto grow" />
    </div>
  );
}

export default LabeledDivider;
