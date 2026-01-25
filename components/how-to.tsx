import {
  MessageCircleQuestionIcon,
  MessageCircleReplyIcon,
  PlusIcon,
  TextSearchIcon,
  VoteIcon,
  WaypointsIcon,
} from 'lucide-react';
import Link from 'next/link';
import ChatActionButtonHighlight from './chat/chat-action-button-highlight';
import { MAX_SELECTABLE_PARTIES } from './chat/chat-group-party-select-content';
import ProConIcon from './chat/pro-con-icon';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './ui/accordion';
import { Button } from './ui/button';

function HowTo() {
  const partySpecificQuestions = [
    'Was ist die Position der SPD zu Klimaschutz?',
    'Wie steht die AfD zur Schuldenbremse?',
    'Wie will die CDU/CSU Bürokratie reduzieren?',
    'Wie wollen die Grünen die Digitalisierung vorantreiben?',
    'Wie wollen die FDP und die Linke die Arbeitszeitreform umsetzen?',
    'Wie wollen Volt und die FDP europäische Zusammenarbeit verbessern?',
  ];

  const compareQuestions = [
    'Wie unterscheiden sich die Parteien im Kampf gegen den Klimawandel?',
    'Wie unterscheiden sich die Positionen der CDU/CSU und der SPD zum Thema Schuldenbremse?',
    'Vergleiche die Positionen der FDP und AfD zum Thema Migration.',
  ];

  const generalQuestions = [
    'Wie kann ich Briefwahl beantragen?',
    'Wer steht hinter wahl.chat?',
    'Wie funktioniert Briefwahl?',
  ];

  const buildQuestionLink = (question: string) => {
    return `/session?q=${question}`;
  };

  return (
    <Accordion type="single" collapsible asChild>
      <article>
        <section>
          <p>
            <span className="font-bold underline">wahl.chat</span> ist ein
            interaktives KI-Tool, das dir hilft, dich über die Positionen und
            Pläne der Parteien zu informieren. Du kannst dem KI-Assistenten
            Fragen zu verschiedenen politischen Themen stellen, und er liefert
            dir neutrale Antworten basierend auf dem{' '}
            <span className="font-bold">
              Grundsatzprogrammen und weiteren Veröffentlichungen der Parteien.
            </span>
            .
          </p>

          <p className="mt-4 text-sm font-semibold">Der Prozess ist einfach:</p>

          <ul className="[&_li]:mt-4 [&_li]:text-sm">
            <li className="relative pl-10">
              <MessageCircleQuestionIcon className="absolute left-0 top-0" />
              Du stellst eine Frage
            </li>
            <li className="relative pl-10">
              <TextSearchIcon className="absolute left-0 top-0" />
              <span className="font-bold underline">wahl.chat</span> durchsucht
              relevante Dokumente wie Grundsatzprogramme, um die passenden
              Informationen zu finden.
            </li>
            <li className="relative pl-10">
              <MessageCircleReplyIcon className="absolute left-0 top-0" />
              Die relevanten Informationen werden dann genutzt, um eine
              verständliche und neutrale Antwort zu generieren.
            </li>
            <li className="relative pl-10">
              <WaypointsIcon className="absolute left-0 top-0" />
              Du kannst dir nun die Position der Partei einordnen lassen indem
              du auf den Knopf unter der Antwort klickst. Oder die Antwort auf
              Basis des Abstimmungsverhaltens der Partei analysieren lassen.
            </li>
          </ul>
        </section>

        <section className="mt-6">
          <AccordionItem value="questions">
            <AccordionTrigger className="font-bold">
              Welche Fragen kann ich stellen?
            </AccordionTrigger>
            <AccordionContent>
              Grundsätzlich kannst du alle Fragen stellen, die du zu den
              Grundsatzprogrammen der Parteien oder ihren Positionen hast.
              Desweiteren kannst du auch Fragen zu generellen Themen wie dem
              Ablauf einer Bundestagswahl stellen.
              <br />
              <br />
              <span className="font-bold">
                Beispiele für Partei-spezifische Fragen:
              </span>
              <ul className="list-outside list-disc py-2 pl-4 [&_li]:pt-1">
                {partySpecificQuestions.map((question) => (
                  <li key={question}>
                    <Link
                      className="underline"
                      href={buildQuestionLink(question)}
                    >
                      {question}
                    </Link>
                  </li>
                ))}
              </ul>
              <br />
              <span className="font-bold">
                Beispiele für vergleichende Fragen:
              </span>
              <ul className="list-outside list-disc py-2 pl-4 [&_li]:pt-1">
                {compareQuestions.map((question) => (
                  <li key={question}>
                    <Link
                      className="underline"
                      href={buildQuestionLink(question)}
                    >
                      {question}
                    </Link>
                  </li>
                ))}
              </ul>
              <br />
              <span className="font-bold">
                Beispiele für allgemeine Fragen:
              </span>
              <ul className="list-outside list-disc py-2 pl-4 [&_li]:pt-1">
                {generalQuestions.map((question) => (
                  <li key={question}>
                    <Link
                      className="underline"
                      href={buildQuestionLink(question)}
                    >
                      {question}
                    </Link>
                  </li>
                ))}
              </ul>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="number-parties">
            <AccordionTrigger className="font-bold">
              Mit wie vielen Parteien kann ich chatten?
            </AccordionTrigger>
            <AccordionContent>
              Du kannst den Chat mit bis zu{' '}
              <span className="font-bold">
                {MAX_SELECTABLE_PARTIES} Parteien
              </span>{' '}
              gleichzeitig starten, hast aber die Möglichkeit während des
              chattens noch weitere Parteien anzusprechen.
              <br />
              <br />
              Desweiteren, kannst du ganz einfach durch den{' '}
              <span className="inline-block">
                <PlusIcon className="size-4 rounded-full bg-primary p-1 text-primary-foreground" />
              </span>{' '}
              knopf über dem Textfeld weitere Parteien zum Chat hinzufügen, oder
              auch wieder entfernen.
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="position">
            <AccordionTrigger className="font-bold">
              Position Einordnen
            </AccordionTrigger>
            <AccordionContent>
              <div className="my-2 flex items-center justify-center">
                <div className="relative rounded-md">
                  <Button
                    variant="outline"
                    className="h-8 px-2 group-data-[has-message-background]:bg-zinc-100 group-data-[has-message-background]:hover:bg-zinc-200 group-data-[has-message-background]:dark:bg-zinc-900 group-data-[has-message-background]:dark:hover:bg-zinc-800"
                    tooltip="Ordne die Position in Pro oder Contra ein"
                    type="button"
                  >
                    <ProConIcon />
                    <span className="text-xs">Position einordnen</span>
                  </Button>
                  <ChatActionButtonHighlight showHighlight />
                </div>
              </div>
              <p>
                Wenn du diesen Knopf unter einer der Nachrichten klickst, wird
                die Position der Nachricht eingeordnet. Dabei werden die
                folgenden Kriterien berücksichtigt: Machbarkeit, Kurzfristige
                und Langfristige Effekte.
                <br />
                Hierbei nutzen wir aktuelle Informationen und Quellen aus dem
                Internet, die uns von Perplexity.ai zur Verfügung gestellt
                werden.
              </p>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="voting-behavior-analyze">
            <AccordionTrigger className="font-bold">
              Abstimmungsverhalten analysieren
            </AccordionTrigger>
            <AccordionContent>
              <div className="my-2 flex items-center justify-center">
                <div className="relative rounded-md">
                  <Button
                    variant="outline"
                    className="h-8 px-2 group-data-[has-message-background]:bg-zinc-100 group-data-[has-message-background]:hover:bg-zinc-200 group-data-[has-message-background]:dark:bg-zinc-900 group-data-[has-message-background]:dark:hover:bg-zinc-800"
                    tooltip="Analysiere das Abstimmungsverhalten der Partei"
                  >
                    <VoteIcon />
                    <span className="text-xs">Abstimmungsverhalten</span>
                  </Button>

                  <ChatActionButtonHighlight showHighlight />
                </div>
              </div>
              <p>
                Wenn du diesen Knopf unter einer der Nachrichten klickst, wird
                das Abstimmungsverhalten der Partei in der Vergangenheit
                analysiert. Darüber hinaus kannst du durch einen Klick auf{' '}
                <span className="italic">
                  &quot;Abstimmungen anzeigen&quot;
                </span>{' '}
                detaillierte Informationen zu den Abstimmungen der Partei sehen.
              </p>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="data">
            <AccordionTrigger className="font-bold">
              Welche Daten werden verwendet?
            </AccordionTrigger>
            <AccordionContent>
              Um fundierte und neutrale Antworten zu liefern, verwendet{' '}
              <span className="font-bold underline">wahl.chat</span> eine
              Vielzahl von Datenquellen:
              <ol className="list-outside list-decimal py-4 pl-4 [&_li]:pt-1">
                <li>
                  <div className="pl-2">
                    <span className="font-bold">
                      Grundsatzprogramme und andere relevante Dokumente:
                    </span>{' '}
                    Neben den Wahlprogrammen werden auch Grundsatzprogramme und
                    weitere von den Parteien stammende Dokumente herangezogen,
                    um ein umfassendes Bild der Parteipositionen zu erhalten.
                  </div>
                </li>
                <li>
                  <div className="pl-2">
                    <span className="font-bold">Positionspapiere:</span> Neben
                    den Grundsatzprogrammen werden auch Wahlprogramme,
                    Positionspapiere und weitere von den Parteien stammende
                    Dokumente herangezogen, um ein umfassendes Bild der
                    Parteipositionen zu erhalten.
                  </div>
                </li>
                <li>
                  <div className="pl-2">
                    <span className="font-bold">
                      Internetquellen für die Einordnung von Positionen:
                    </span>{' '}
                    Für die differenzierte Einordnung von Positionen nutzt{' '}
                    <span className="font-bold underline">wahl.chat</span> den
                    Dienst Perplexity.ai, der hochwertige Internetquellen wie
                    Nachrichtenseiten verwendet.
                  </div>
                </li>
              </ol>
              <br />
              Wir haben alle Quellen die{' '}
              <span className="font-bold underline">wahl.chat</span> nutzt{' '}
              <Link href="/sources" className="underline">
                hier
              </Link>{' '}
              aufgelistet.
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="guidelines">
            <AccordionTrigger className="font-bold">
              Welchen Leitlinien folgt wahl.chat in seinen Antworten?
            </AccordionTrigger>
            <AccordionContent>
              Folgende Leitlinien gelten für die Antworten in den Chats:
              <ol className="list-outside list-decimal py-4 pl-4 [&_li]:pt-1">
                <li>
                  <div className="pl-2">
                    <span className="font-bold">Quellenbassiert:</span> Die
                    Antworten sollen auf den relevanten Aussagen aus den
                    bereitgestellten Programmauszügen beruhen.
                  </div>
                </li>
                <li>
                  <div className="pl-2">
                    <span className="font-bold">Neutralität:</span>{' '}
                    Parteipositionen sollen neutral und ohne Wertung
                    wiedergegeben werden.
                  </div>
                </li>
                <li>
                  <div className="pl-2">
                    <span className="font-bold">Transparenz:</span> Zu jeder
                    Aussage sollen direkt die relevanten Quellen verlinkt
                    werden, um eine detaillierte Betrachtung und Überprüfung des
                    Inhalts zu ermöglichen.
                  </div>
                </li>
              </ol>
            </AccordionContent>
          </AccordionItem>
          <AccordionItem value="party-selection">
            <AccordionTrigger className="font-bold">
              Nach welchen Kriterien werden die Parteien ausgewählt?
            </AccordionTrigger>
            <AccordionContent>
              Die urspüngliche Auswahl der Parteien erfolgte vor der
              Bundestagswahl 2025 und orientierte sich an der Veröffentlichung
              ihrer Wahlprogramme. Wir wollen nun nach und nach die noch
              fehlenden Parteien hinzufügen, und freuen uns sehr über eure
              Mithilfe.
              <br />
              <br />
              Solltest du eine Partei vermissen, schreibe uns gerne eine E-Mail
              mit ihrem Grundsatzprogramm als PDF im Anhang an{' '}
              <a href="mailto:info@wahl.chat" className="underline">
                info@wahl.chat
              </a>
              , und wir werden sie so schnell wie möglich ergänzen.
            </AccordionContent>
          </AccordionItem>
        </section>
      </article>
    </Accordion>
  );
}

export default HowTo;
