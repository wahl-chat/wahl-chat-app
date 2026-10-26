import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from '@/components/chat/responsive-drawer-dialog';
import { Link } from '@/i18n/navigation';
import { cn } from '@/lib/utils';
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  CpuIcon,
  DatabaseIcon,
  GitBranch,
} from 'lucide-react';
import { useTranslations } from 'next-intl';

const bold = (chunks: React.ReactNode) => (
  <span className="font-semibold">{chunks}</span>
);

const privacyLink = (chunks: React.ReactNode) => (
  <Link href="/datenschutz" className="font-semibold underline">
    {chunks}
  </Link>
);

const POINTS = [
  { key: 'automated', Icon: CpuIcon },
  { key: 'notOfficial', Icon: AlertCircleIcon },
  { key: 'nuance', Icon: GitBranch },
  { key: 'inaccuracies', Icon: AlertTriangleIcon },
  { key: 'storage', Icon: DatabaseIcon },
] as const;

function AiDisclaimerContent() {
  const t = useTranslations('disclaimer');

  return (
    <div className="px-4 pb-4 text-sm text-foreground md:px-0 md:pb-0">
      <p>{t.rich('intro', { b: bold })}</p>

      <ul className="flex list-inside flex-col gap-4 py-4 *:flex *:items-center *:gap-2">
        {POINTS.map(({ key, Icon }) => (
          <li key={key}>
            <Icon className="mr-2 size-6 shrink-0" />
            <span className="inline-block">
              {t.rich(key, { b: bold, link: privacyLink })}
            </span>
          </li>
        ))}
      </ul>

      <p>{t.rich('outro', { b: bold })}</p>
    </div>
  );
}

type Props = {
  className?: string;
};

function AiDisclaimer({ className }: Props) {
  const t = useTranslations('disclaimer');

  return (
    <ResponsiveDialog>
      <p
        className={cn(
          'my-2 text-center text-xs text-muted-foreground',
          className,
        )}
      >
        {t('notice')}{' '}
        <ResponsiveDialogTrigger className="font-semibold underline">
          {t('learnMore')}
        </ResponsiveDialogTrigger>
      </p>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{t('title')}</ResponsiveDialogTitle>
        </ResponsiveDialogHeader>
        <AiDisclaimerContent />
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default AiDisclaimer;
