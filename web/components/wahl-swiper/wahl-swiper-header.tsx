import Logo from '@/components/chat/logo';
import { Separator } from '@/components/ui/separator';
import Link from 'next/link';
import WahlSwiperContextSelector from './wahl-swiper-context-selector';

type Props = {
  contextId: string;
};

function WahlSwiperHeader({ contextId }: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background">
      <div className="mx-auto flex h-header w-full max-w-xl items-center gap-2 px-4 md:px-0">
        <Link href={`/${contextId}`} aria-label="Zur Startseite">
          <Logo className="size-10 md:size-12" />
        </Link>
        <Separator orientation="vertical" className="h-6" />
        <WahlSwiperContextSelector />
      </div>
    </header>
  );
}

export default WahlSwiperHeader;
