import GithubIcon from '@/components/icons/github-icon';
import { Button } from '@/components/ui/button';
import Link from 'next/link';

function GitHubCard({ fullWidth = false }: { fullWidth?: boolean }) {
  return (
    <div
      className={`flex flex-col rounded-md border border-border${
        fullWidth ? ' md:col-span-2' : ''
      }`}
    >
      <div className="flex grow flex-col justify-between p-4">
        <div>
          <h2 className="font-bold">
            Der Code hinter <span className="underline">wahl.chat</span>
          </h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Du willst wissen wie <span className="underline">wahl.chat</span>{' '}
            funktioniert oder sogar selbst mitentwickeln? Der gesamte Code ist
            Open Source und auf GitHub verfügbar.
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
