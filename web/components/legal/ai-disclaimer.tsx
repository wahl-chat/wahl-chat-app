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

type Variant = 'chat' | 'feed';

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
] as const;

function AiDisclaimerContent({ variant }: { variant: Variant }) {
  const t = useTranslations('disclaimer');
  // Only the chat stores what the reader writes.
  const points =
    variant === 'chat'
      ? [...POINTS, { key: 'storage', Icon: DatabaseIcon } as const]
      : POINTS;

  return (
    <div className="min-h-0 overflow-y-auto overscroll-contain px-4 pb-4 text-sm text-foreground md:px-0 md:pb-0">
      <p>{t.rich(`intro.${variant}`, { b: bold })}</p>

      <ul className="flex list-inside flex-col gap-4 py-4 *:flex *:items-center *:gap-2">
        {points.map(({ key, Icon }) => (
          <li key={key}>
            <Icon className="mr-2 size-6 shrink-0" />
            <span className="inline-block">
              {t.rich(key, { b: bold, link: privacyLink })}
            </span>
          </li>
        ))}
      </ul>

      <p>{t.rich(`outro.${variant}`, { b: bold })}</p>
    </div>
  );
}

type Props = {
  className?: string;
  variant?: Variant;
};

function AiDisclaimer({ className, variant = 'chat' }: Props) {
  const t = useTranslations('disclaimer');

  return (
    <ResponsiveDialog>
      <p
        className={cn(
          'my-2 text-center text-xs text-muted-foreground',
          className,
        )}
      >
        {t(`notice.${variant}`)}{' '}
        <ResponsiveDialogTrigger className="font-semibold underline">
          {t(`learnMore.${variant}`)}
        </ResponsiveDialogTrigger>
      </p>
      <ResponsiveDialogContent className="flex max-h-[90dvh] flex-col">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{t('title')}</ResponsiveDialogTitle>
        </ResponsiveDialogHeader>
        <AiDisclaimerContent variant={variant} />
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default AiDisclaimer;
