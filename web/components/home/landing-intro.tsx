import type { Context } from '@/lib/firebase/firebase.types';
import { formatGermanDate } from '@/lib/utils';
import Link from 'next/link';

type Props = {
  upcoming: Context[];
  past: Context[];
};

function ElectionLinkList({ contexts }: { contexts: Context[] }) {
  return (
    <ul className="space-y-1">
      {contexts.map((context) => {
        const date = formatGermanDate(context.date);

        return (
          <li key={context.context_id}>
            <Link
              href={`/${context.context_id}`}
              className="font-medium text-foreground underline"
            >
              {context.name}
            </Link>
            {date && <span> – {date}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Prose and the full election index, below the interactive surface.
 *
 * The links matter as much as the text: / carries the site's inbound links, so
 * it is the page best placed to pass authority on to each election page.
 */
function LandingIntro({ upcoming, past }: Props) {
  return (
    <section className="mt-8 space-y-4 text-sm text-muted-foreground">
      <h2 className="text-xl font-bold text-foreground md:text-2xl">
        Was ist wahl.chat?
      </h2>

      <p>
        wahl.chat ist ein KI-Assistent, dem du deine Fragen zu den Positionen
        verschiedener Parteien stellen kannst. Statt dich durch hunderte Seiten
        Wahlprogramm oder Plenarprotokoll zu arbeiten, fragst du einfach nach
        dem, was dich interessiert - Mieten, Bildung, Klima, Wirtschaft,
        Migration - und bekommst eine Antwort zu genau dieser Frage. Du kannst
        mehrere Parteien gleichzeitig auswählen und ihre Positionen zum selben
        Thema direkt nebeneinander vergleichen.
      </p>

      <p>
        Jede Antwort ist mit Quellen belegt: wahl.chat zitiert die Stellen aus
        den verfügbaren Dokumenten, auf denen sie beruht, und du kannst sie mit
        einem Klick im Original nachlesen. Anders als beim Wahl-O-Mat
        beantwortest du keine vorgegebenen Thesen, sondern fragst selbst, was
        dich interessiert und hakst nach, wenn dir etwas zu vage ist. Wie das
        funktioniert, erklärt die{' '}
        <Link href="/how-to" className="font-medium underline">
          Anleitung
        </Link>
        . Wer dahintersteht, steht{' '}
        <Link href="/about-us" className="font-medium underline">
          über uns
        </Link>
        .
      </p>

      {upcoming.length > 0 && (
        <>
          <h3 className="pt-2 font-bold text-foreground">Kommende Wahlen</h3>
          <ElectionLinkList contexts={upcoming} />
        </>
      )}

      {past.length > 0 && (
        <>
          <h3 className="pt-2 font-bold text-foreground">Vergangene Wahlen</h3>
          <ElectionLinkList contexts={past} />
        </>
      )}

      <p>
        Die Antworten werden von einer künstlichen Intelligenz auf Basis
        öffentlicher Parteidokumente erzeugt und sind keine offiziellen Aussagen
        der Parteien. Deine Nachrichten werden gespeichert, um die Antworten zu
        erzeugen und dir deinen Chatverlauf anzuzeigen – Details dazu stehen in
        der{' '}
        <Link href="/datenschutz" className="font-medium underline">
          Datenschutzerklärung
        </Link>
        .
      </p>
    </section>
  );
}

export default LandingIntro;
