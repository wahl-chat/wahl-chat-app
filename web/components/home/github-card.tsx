import GithubIcon from '@/components/icons/github-icon';
import { Button } from '@/components/ui/button';
import { Link } from '@/i18n/navigation';
import { useTranslations } from 'next-intl';

function GitHubCard({
  fullWidth = false,
  titleAs: Title = 'h2',
}: {
  fullWidth?: boolean;
  /** h3 under a landing-page section heading; h2 as a top-level card. */
  titleAs?: 'h2' | 'h3';
}) {
  const t = useTranslations('home.githubCard');

  return (
    <div
      className={`flex flex-col rounded-md border border-border${
        fullWidth ? ' md:col-span-2' : ''
      }`}
    >
      <div className="flex grow flex-col justify-between p-4">
        <div>
          <Title className="font-bold">
            {t.rich('title', {
              underline: (chunks) => (
                <span className="underline">{chunks}</span>
              ),
            })}
          </Title>
          <p className="mb-4 text-sm text-muted-foreground">
            {t.rich('description', {
              underline: (chunks) => (
                <span className="underline">{chunks}</span>
              ),
            })}
          </p>
        </div>
        <Button asChild variant="secondary" className="w-full">
          <Link
            href="https://github.com/wahl-chat"
            target="_blank"
            rel="noopener noreferrer"
          >
            <GithubIcon className="size-5" />
            GitHub
          </Link>
        </Button>
      </div>
    </div>
  );
}

export default GitHubCard;
