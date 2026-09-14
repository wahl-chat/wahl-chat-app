import type { Context } from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import { formatGermanDate } from '@/lib/utils';
import Link from 'next/link';

type Props = {
  context: Context;
  parties?: PartyDetails[];
};

function formatPartyList(parties: PartyDetails[]): string {
  const names = parties.map((party) => party.name);

  if (names.length <= 1) return names.join('');

  return `${names.slice(0, -1).join(', ')} und ${names[names.length - 1]}`;
}

/**
 * Crawlable prose about the election, rendered below the interactive surface.
 *
 * Placement is deliberate: search engines read the whole document regardless of
 * visual order, so the selector and chat input keep the top of the page while
 * the page still carries enough text to be understood as being about this
 * election.
 */
function ContextIntro({ context, parties }: Props) {
  const electionDate = formatGermanDate(context.date);
  const partyList = parties?.length ? formatPartyList(parties) : undefined;

  return (
    <section className="mt-8 space-y-4 text-sm text-muted-foreground">
      <h2 className="text-xl font-bold text-foreground md:text-2xl">
        {context.name} – Parteipositionen im Chat vergleichen
      </h2>

      <p>
        {electionDate
          ? `Am ${electionDate} wird in ${context.location_name} gewählt. `
          : `In ${context.location_name} stehen politische Entscheidungen an. `}
        Auf wahl.chat kannst du den Parteien deine eigenen Fragen stellen – zu
        Mieten, Bildung, Klima, Wirtschaft oder jedem anderen Thema, das dich
        beschäftigt. Statt dich durch hunderte Seiten Wahlprogramm zu arbeiten,
        bekommst du eine Antwort auf genau die Frage, die du gestellt hast.
      </p>

      {partyList && (
        <p>
          Für die {context.name} kannst du mit {partyList} chatten. Du kannst
          auch mehrere Parteien gleichzeitig auswählen und ihre Positionen zum
          selben Thema direkt nebeneinander vergleichen.
        </p>
      )}

      <p>
        Jede Antwort ist mit Quellen belegt: wahl.chat zitiert die Stellen aus
        den Wahl- und Parteiprogrammen, auf denen die Antwort beruht, und du
        kannst sie mit einem Klick im Original nachlesen. Welche Dokumente
        dahinterstehen, findest du auf der{' '}
        <Link
          href={`/${context.context_id}/sources`}
          className="font-medium underline"
        >
          Quellenseite
        </Link>
        .
      </p>

      <p>
        Anders als beim Wahl-O-Mat beantwortest du keine vorgegebenen Thesen. Du
        bestimmst selbst, worüber gesprochen wird, und kannst nachfragen, wenn
        dir eine Antwort zu vage ist. Wie das genau funktioniert, erklärt die{' '}
        <Link href="/how-to" className="font-medium underline">
          Anleitung
        </Link>
        .
      </p>

      <p>
        Die Antworten werden von einer künstlichen Intelligenz erzeugt und sind
        keine offiziellen Aussagen der Parteien. Deine Nachrichten werden
        gespeichert, um die Antworten zu erzeugen und dir deinen Chatverlauf
        anzuzeigen – Details dazu stehen in der{' '}
        <Link href="/datenschutz" className="font-medium underline">
          Datenschutzerklärung
        </Link>
        .
      </p>
    </section>
  );
}

export default ContextIntro;
