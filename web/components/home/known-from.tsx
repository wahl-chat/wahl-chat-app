import ComputerBildIcon from '@/components/icons/computer-bild-icon';
import HandelsblattIcon from '@/components/icons/handelsblatt-icon';
import SWRIcon from '@/components/icons/swr-icon';
import ZdfHeuteIcon from '@/components/icons/zdf-heute-icon';
import { Separator } from '@/components/ui/separator';

function KnownFrom() {
  const iconClassNames =
    'size-full px-[0%] opacity-50 grayscale hover:opacity-100 hover:grayscale-0 transition-all duration-300 ease-in-out';

  return (
    <section className="my-6 flex w-full flex-col items-center justify-center gap-4 md:mt-2">
      <div className="flex w-full flex-row items-center gap-4">
        <Separator className="w-auto grow" />
        <p className="text-xs font-medium text-muted-foreground opacity-50">
          Bekannt aus:
        </p>
        <Separator className="w-auto grow" />
      </div>
      <div className="grid h-16 w-full grid-cols-4 items-center justify-center gap-8">
        <HandelsblattIcon className={iconClassNames} />
        <ZdfHeuteIcon className={iconClassNames} />
        <SWRIcon className={iconClassNames} />
        <ComputerBildIcon className={iconClassNames} />
        {/* <SWRIcon className={iconClassNames} />
        <SueddeutscheZeitungIcon className={iconClassNames} /> */}
      </div>
      <Separator className="mt-2 w-full" />
    </section>
  );
}

export default KnownFrom;
