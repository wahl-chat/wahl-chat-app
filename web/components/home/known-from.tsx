import ComputerBildIcon from '@/components/icons/computer-bild-icon';
import MerkurTzIcon from '@/components/icons/merkur-tz-icon';
import SWRIcon from '@/components/icons/swr-icon';
import ZdfHeuteIcon from '@/components/icons/zdf-heute-icon';
import LabeledDivider from '@/components/labeled-divider';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

type Props = {
  className?: string;
  /**
   * Closes the band off at the bottom. Wanted on the context home page, where
   * the cards follow straight after; dropped on the landing page, where the
   * stats bring their own labelled divider and two rules would stack up.
   */
  trailingSeparator?: boolean;
};

function KnownFrom({ className, trailingSeparator = true }: Props) {
  const iconClassNames =
    'size-full px-[0%] opacity-50 grayscale hover:opacity-100 hover:grayscale-0 transition-all duration-300 ease-in-out';

  return (
    <section
      className={cn(
        'my-6 flex w-full flex-col items-center justify-center gap-4 md:mt-2',
        className,
      )}
    >
      <LabeledDivider>Bekannt aus:</LabeledDivider>
      <div className="grid h-16 w-full grid-cols-4 items-center justify-center gap-8">
        <MerkurTzIcon className={iconClassNames} />
        <ZdfHeuteIcon className={iconClassNames} />
        <SWRIcon className={iconClassNames} />
        <ComputerBildIcon className={iconClassNames} />
        {/* <SWRIcon className={iconClassNames} />
        <SueddeutscheZeitungIcon className={iconClassNames} /> */}
      </div>
      {trailingSeparator && <Separator className="mt-2 w-full" />}
    </section>
  );
}

export default KnownFrom;
