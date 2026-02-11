'use client';

import { Button } from '@/components/ui/button';
import { BugIcon } from 'lucide-react';

export type ErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

function ErrorView({ error, reset }: ErrorProps) {
  return (
    <div className="flex size-full flex-col items-center justify-center gap-2 px-4">
      <BugIcon className="size-12 text-destructive" />
      <h1 className="text-center text-2xl font-bold">
        Oops!
        <br />
        Etwas ist schief gelaufen.
      </h1>
      <p className="text-center text-sm text-muted-foreground">
        {error.message}
      </p>
      <Button onClick={reset} className="mt-2">
        Versuche es erneut
      </Button>
    </div>
  );
}

export default ErrorView;
