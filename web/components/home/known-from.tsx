import ComputerBildIcon from '@/components/icons/computer-bild-icon';
import MerkurTzIcon from '@/components/icons/merkur-tz-icon';
import SWRIcon from '@/components/icons/swr-icon';
import ZdfHeuteIcon from '@/components/icons/zdf-heute-icon';
import LabeledDivider from '@/components/labeled-divider';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

/**
 * Each logo links to the piece that outlet ran about wahl.chat.
 *
 * The link carries the outlet's name because three of the four marks are
 * wordmarks with no <title>, so the logo alone gives a screen reader nothing to
 * announce — and "link, image" is the least useful thing a press strip can say.
 */
const PRESS_MENTIONS = [
  {
    name: 'tz',
    Icon: MerkurTzIcon,
    href: 'https://www.tz.de/muenchen/stadt/dieser-ki-chatbot-beantwortet-alle-ihre-fragen-zur-muenchen-wahl-exklusiv-auf-tz-de-zr-94172777.html',
  },
  {
    name: 'ZDFheute',
    Icon: ZdfHeuteIcon,
    href: 'https://www.zdfheute.de/politik/deutschland/alternative-wahl-o-mat-100.html',
  },
  {
    name: 'SWR',
    Icon: SWRIcon,
    href: 'https://www.swr.de/swraktuell/wahlen/bundestagswahl/wahlomat-alternative-ki-wahlentscheidung-hilfe-gefahr-sicher-100.html',
  },
  {
    name: 'COMPUTER BILD',
    Icon: ComputerBildIcon,
    href: 'https://www.computerbild.de/artikel/cb-News-Internet-Mit-KI-zum-Kanzler-WahlChat-verraet-was-SPD-CDU-Co-in-ihren-Progammen-versprechen-39356257.html',
  },
];

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
  // The hover state is driven from the link rather than the mark itself, so
  // the whole cell reacts and not just the glyphs the pointer happens to be on.
  const iconClassNames =
    'size-full px-[0%] opacity-50 grayscale group-hover:opacity-100 group-hover:grayscale-0 group-focus-visible:opacity-100 group-focus-visible:grayscale-0 transition-all duration-300 ease-in-out';

  return (
    <section
      className={cn(
        'my-6 flex w-full flex-col items-center justify-center gap-4 md:mt-2',
        className,
      )}
    >
      <LabeledDivider>Bekannt aus:</LabeledDivider>
      <nav aria-label="Presseberichte über wahl.chat">
        <ul className="grid h-16 w-full grid-cols-4 items-center justify-center gap-8">
          {PRESS_MENTIONS.map(({ name, Icon, href }) => (
            <li key={name} className="flex h-full items-center justify-center">
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Bericht über wahl.chat bei ${name}`}
                className="group flex size-full items-center justify-center rounded-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <Icon className={iconClassNames} />
              </a>
            </li>
          ))}
        </ul>
      </nav>
      {trailingSeparator && <Separator className="mt-2 w-full" />}
    </section>
  );
}

export default KnownFrom;
