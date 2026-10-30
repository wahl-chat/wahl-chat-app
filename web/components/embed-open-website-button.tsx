import { Link } from '@/i18n/navigation';
import { useTranslations } from 'next-intl';
import Logo from './chat/logo';
import MessageLoadingBorderTrail from './chat/message-loading-border-trail';
import { Button } from './ui/button';

function EmbedOpenWebsiteButton() {
  const t = useTranslations('common');

  return (
    <Button variant="outline" size="sm" asChild className="relative">
      <Link target="_blank" href="https://wahl.chat">
        <MessageLoadingBorderTrail />
        <Logo variant="small" className="size-4" />
        {t('openWebsite')}
      </Link>
    </Button>
  );
}

export default EmbedOpenWebsiteButton;
