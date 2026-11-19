import Logo from '@/components/chat/logo';
import RtlIcon from '@/components/icons/rtl-icon';
import { Button } from '@/components/ui/button';
import { Link } from '@/i18n/navigation';
import { LibraryBigIcon, XIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';

function SidebarTvTeaser() {
  const t = useTranslations('chat.sidebar.tvTeaser');
  return (
    <div className="relative mt-4 overflow-hidden rounded-md border border-border bg-muted p-6 text-center">
      <div className="grid w-full grid-cols-[1fr_auto_1fr] items-center justify-center gap-4">
        <Logo className="ml-auto w-12" />
        <XIcon className="size-4" />
        <RtlIcon className="mr-auto w-24" />
      </div>

      <p className="mt-2 text-sm text-black/70 dark:text-white/70">
        {t('missed')} <br /> {t('compare')}
      </p>

      <Button className="relative z-10 mt-2" asChild>
        <Link href="/topics">
          <LibraryBigIcon />
          {t('cta')}
        </Link>
      </Button>
    </div>
  );
}

export default SidebarTvTeaser;
