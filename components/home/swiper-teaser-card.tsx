import Logo from '@/components/chat/logo';
import { Button } from '@/components/ui/button';
import { ArrowRightIcon } from 'lucide-react';
import Link from 'next/link';
import WahlSwiperTeaserVector from './wahl-swiper-teaser-vector';

function SwiperTeaserCard() {
  return (
    <div className="relative h-[250px] overflow-hidden rounded-md border border-border bg-muted p-6 text-center md:col-span-2 md:h-[174px] md:text-left">
      <div className="flex items-center justify-center gap-2 md:justify-normal">
        <Logo className="w-6" variant="small" />
        <p className="text-lg font-bold italic">Swiper</p>
      </div>

      <p className="mt-2 text-sm text-black/70 dark:text-white/70">
        Finde jetzt die passende Partei.
      </p>

      <Button className="relative z-10 mt-2" asChild>
        <Link href="/swiper">
          Wahl Swiper
          <ArrowRightIcon className="size-4" />
        </Link>
      </Button>

      <div className="absolute inset-x-0 bottom-[-36px] mx-auto w-[90%] max-w-[285px] md:absolute md:bottom-auto md:left-auto md:right-0 md:top-0 md:mx-0 md:w-1/3 md:rotate-12 md:scale-125">
        <WahlSwiperTeaserVector />
      </div>
    </div>
  );
}

export default SwiperTeaserCard;
