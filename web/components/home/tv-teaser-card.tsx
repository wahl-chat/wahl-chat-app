import Logo from '@/components/chat/logo';
import RtlIcon from '@/components/icons/rtl-icon';
import { Button } from '@/components/ui/button';
import { LibraryBigIcon, XIcon } from 'lucide-react';
import { getImageProps } from 'next/image';
import Link from 'next/link';

function TvTeaserCard() {
  const imageProps = {
    alt: 'Candidates',
    className: 'size-full h-auto w-full object-contain',
    sizes: '100vw',
    width: 200,
    height: 100,
  };
  const {
    props: { srcSet: mobile },
  } = getImageProps({ ...imageProps, src: '/images/candidates-mobile.webp' });
  const {
    props: { srcSet: desktop, ...rest },
  } = getImageProps({ ...imageProps, src: '/images/candidates.webp' });

  return (
    <div className="relative h-[266px] overflow-hidden rounded-md border border-border bg-muted p-6 text-center md:col-span-2 md:h-[174px] md:text-left">
      <div className="grid w-full grid-cols-[1fr_auto_1fr] items-center justify-center gap-4 md:flex md:w-fit">
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

      <div className="absolute inset-x-0 bottom-0 z-0 mx-auto flex max-w-[380px] items-center justify-center md:ml-auto md:mr-0 md:w-1/2 md:max-w-none md:justify-end">
        <picture>
          <source media="(min-width: 768px)" srcSet={desktop} />
          <source media="(max-width: 767px)" srcSet={mobile} />
          <img {...rest} alt="Candidates" />
        </picture>
      </div>
    </div>
  );
}

export default TvTeaserCard;
