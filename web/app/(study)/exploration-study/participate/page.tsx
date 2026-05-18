import type { Metadata } from 'next';
import { ParticipateRedirect } from './participate-redirect';

const MAILTO = 'mailto:paul@mwlampe.de';
const TITLE = 'Um an der Studie teilzunehmen, hier klicken';
const DESCRIPTION = 'Du wirst weitergeleitet, um eine E-Mail zu senden.';

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: TITLE,
    description: DESCRIPTION,
  },
};

export default function ParticipatePage() {
  return (
    <main className="flex min-h-dvh items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border bg-card p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold">{TITLE}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{DESCRIPTION}</p>
        <ParticipateRedirect href={MAILTO} />
      </div>
    </main>
  );
}
