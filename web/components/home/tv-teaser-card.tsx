import Logo from '@/components/chat/logo';
import RtlIcon from '@/components/icons/rtl-icon';
import { Button } from '@/components/ui/button';
import { Link } from '@/i18n/navigation';
import { LibraryBigIcon, XIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { getImageProps } from 'next/image';

function TvTeaserCard() {
  const t = useTranslations('home.tvTeaserCard');
  const imageProps = {
    alt: t('imageAlt'),
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
        {t.rich('description', { br: () => <br /> })}
      </p>

      <Button className="relative z-10 mt-2" asChild>
        <Link href="/topics">
          <LibraryBigIcon />
          {t('button')}
        </Link>
      </Button>

      <div className="absolute inset-x-0 bottom-0 z-0 mx-auto flex max-w-[380px] items-center justify-center md:ml-auto md:mr-0 md:w-1/2 md:max-w-none md:justify-end">
        <picture>
          <source media="(min-width: 768px)" srcSet={desktop} />
          <source media="(max-width: 767px)" srcSet={mobile} />
          <img {...rest} alt={t('imageAlt')} />
        </picture>
      </div>
    </div>
  );
}

export default TvTeaserCard;
