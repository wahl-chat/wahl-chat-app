import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from '@/components/chat/responsive-drawer-dialog';
import { cn } from '@/lib/utils';
import {
  AlertCircleIcon,
  AlertTriangleIcon,
  CpuIcon,
  DatabaseIcon,
  GitBranch,
} from 'lucide-react';
import Link from 'next/link';

function AiDisclaimerContent() {
  return (
    <div className="px-4 pb-4 text-sm text-foreground md:px-0 md:pb-0">
      <p>
        Die Antworten auf wahl.chat werden von einer{' '}
        <span className="font-semibold">künstlichen Intelligenz</span>{' '}
        generiert. Sie basieren auf Informationen, die aus{' '}
        <span className="font-semibold">öffentlich zugänglichen Partei-</span>{' '}
        und <span className="font-semibold">Wahlprogrammen</span> extrahiert
        wurden. Während wahl.chat bestrebt ist, genaue Informationen über
        Parteipositionen und -werte zu liefern, gilt:
      </p>

      <ul className="flex list-inside flex-col gap-4 py-4 *:flex *:items-center *:gap-2">
        <li>
          <CpuIcon className="mr-2 size-6 shrink-0" />
          <span className="inline-block">
            Die{' '}
            <span className="font-semibold">Verarbeitung und Generierung</span>{' '}
            aller Inhalte erfolgt{' '}
            <span className="font-semibold">automatisiert.</span>
          </span>
        </li>
        <li>
          <AlertCircleIcon className="mr-2 size-6 shrink-0" />
          <span className="inline-block">
            Die Antworten sind{' '}
            <span className="font-semibold">
              nicht als offizielle Parteiaussagen
            </span>{' '}
            zu verstehen.
          </span>
        </li>
        <li>
          <GitBranch className="mr-2 size-6 shrink-0" />
          <span className="inline-block">
            <span className="font-semibold">
              Komplexe politische Positionen
            </span>{' '}
            können eventuell nicht in allen Nuancen erfasst werden.
          </span>
        </li>
        <li>
          <AlertTriangleIcon className="mr-2 size-6 shrink-0" />
          <span className="inline-block">
            <span className="font-semibold">Ungenauigkeiten</span> oder{' '}
            <span className="font-semibold">Fehlinterpretationen</span> können
            gelegentlich auftreten.
          </span>
        </li>
        <li>
          <DatabaseIcon className="mr-2 size-6 shrink-0" />
          <span className="inline-block">
            <span className="font-semibold">
              Deine Nachrichten werden gespeichert
            </span>
            , um die Antworten zu erzeugen und dir deinen Chatverlauf
            anzuzeigen. Mehr dazu in der{' '}
            <Link href="/datenschutz" className="font-semibold underline">
              Datenschutzerklärung
            </Link>
            .
          </span>
        </li>
      </ul>

      <p>
        Dieser KI-Chat dient als{' '}
        <span className="font-semibold">Bildungswerkzeug</span>, um verschiedene
        politische Positionen kennenzulernen. Für{' '}
        <span className="font-semibold">verbindliche Informationen</span> nutzen
        Sie bitte die{' '}
        <span className="font-semibold">offiziellen Parteiquellen</span>.
      </p>
    </div>
  );
}

type Props = {
  className?: string;
};

function AiDisclaimer({ className }: Props) {
  return (
    <ResponsiveDialog>
      <p className="my-2 text-center text-xs text-muted-foreground">
        wahl.chat Antwortet mit KI.{' '}
        <ResponsiveDialogTrigger className="font-semibold underline">
          Erfahre hier mehr.
        </ResponsiveDialogTrigger>
      </p>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>KI Hinweis</ResponsiveDialogTitle>
        </ResponsiveDialogHeader>
        <AiDisclaimerContent />
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default AiDisclaimer;
