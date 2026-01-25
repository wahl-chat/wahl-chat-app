import Logo from '@/components/chat/logo';
import RtlIcon from '@/components/icons/rtl-icon';
import { Button } from '@/components/ui/button';
import { LibraryBigIcon, XIcon } from 'lucide-react';
import Link from 'next/link';

function SidebarTvTeaser() {
  return (
    <div className="relative mt-4 overflow-hidden rounded-md border border-border bg-muted p-6 text-center">
      <div className="grid w-full grid-cols-[1fr_auto_1fr] items-center justify-center gap-4">
        <Logo className="ml-auto w-12" />
        <XIcon className="size-4" />
        <RtlIcon className="mr-auto w-24" />
      </div>

      <p className="mt-2 text-sm text-black/70 dark:text-white/70">
        Beim Quadrell nicht dabei gewesen? <br /> Vergleiche die Themen bei uns.
      </p>

      <Button className="relative z-10 mt-2" asChild>
        <Link href="/topics">
          <LibraryBigIcon />
          Aktuelle Themen
        </Link>
      </Button>
    </div>
  );
}

export default SidebarTvTeaser;
