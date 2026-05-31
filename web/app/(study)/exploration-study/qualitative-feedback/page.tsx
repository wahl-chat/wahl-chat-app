import { MessagesSquare } from 'lucide-react';
import type { Metadata } from 'next';

const TITLE = 'Qualitatives Feedback';
const DESCRIPTION = 'Du hast die Aufgabe abgeschlossen.';

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
};

/**
 * Terminal page for the qualitative study. Participants land here after the
 * task ends (the questionnaire route forwards qualitative sessions here). It is
 * a deliberately static placeholder: there is no questionnaire, quiz, or
 * demographics step — the moderator takes over the conversation live.
 *
 * It lives as a sibling of the `[sessionId]` route group so it sits outside the
 * session-state redirect guard, which would otherwise bounce participants back
 * to the questionnaire route.
 */
export default function QualitativeFeedbackPage() {
  return (
    <main className="flex min-h-dvh items-center justify-center p-4">
      <div className="w-full max-w-lg space-y-6 rounded-lg border bg-card p-8 text-center shadow-sm">
        <div className="flex justify-center">
          <MessagesSquare aria-hidden="true" className="size-14 text-primary" />
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl font-bold">{TITLE}</h1>
          <p className="text-muted-foreground">
            Vielen Dank – du hast die Aufgabe abgeschlossen.
          </p>
        </div>

        <p className="text-sm text-muted-foreground">
          Im nächsten Schritt sprechen wir gemeinsam über deine Erfahrungen mit
          dem System. Bitte lass dieses Fenster geöffnet – die Moderation führt
          dich durch das Gespräch.
        </p>
      </div>
    </main>
  );
}
