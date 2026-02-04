'use client';

import { exportHowToPDF } from '@/lib/how-to-pdf-export';
import {
  DownloadIcon,
  MessageCircleQuestionIcon,
  MessageCircleReplyIcon,
  PlusIcon,
  TextSearchIcon,
  VoteIcon,
  WaypointsIcon,
} from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';
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

// Content configuration - single source of truth
const PARTY_SPECIFIC_QUESTIONS = [
  'Was ist die Position der SPD zu Klimaschutz?',
  'Wie steht die AfD zur Schuldenbremse?',
  'Wie will die CDU/CSU Bürokratie reduzieren?',
  'Wie wollen die Grünen die Digitalisierung vorantreiben?',
  'Wie wollen die FDP und die Linke die Arbeitszeitreform umsetzen?',
  'Wie wollen Volt und die FDP europäische Zusammenarbeit verbessern?',
];

const COMPARE_QUESTIONS = [
  'Wie unterscheiden sich die Parteien im Kampf gegen den Klimawandel?',
  'Wie unterscheiden sich die Positionen der CDU/CSU und der SPD zum Thema Schuldenbremse?',
  'Vergleiche die Positionen der FDP und AfD zum Thema Migration.',
];

const GENERAL_QUESTIONS = [
  'Wie kann ich Briefwahl beantragen?',
  'Wer steht hinter wahl.chat?',
  'Wie funktioniert Briefwahl?',
];

const INTRO_TEXT = {
  main: 'wahl.chat ist ein interaktives KI-Tool, das dir hilft, dich über die Positionen und Pläne der Parteien zu informieren. Du kannst dem KI-Assistenten Fragen zu verschiedenen politischen Themen stellen, und er liefert dir neutrale Antworten basierend auf den Wahlprogrammen und weiteren Veröffentlichungen der Parteien.',
  sources:
    'Alle Antworten sind mit den entsprechenden Quellen versehen und nutzen für die ausgewählte Wahl relevante Dokumente.',
};

const PROCESS_STEPS = [
  'Du stellst eine Frage',
  'wahl.chat durchsucht relevante Dokumente wie Wahl- und Grundsatzprogramme, um die passenden Informationen zu finden.',
  'Die relevanten Informationen werden dann genutzt, um eine verständliche und quellenbasierte Antwort zu generieren.',
  'Du kannst dir nun die Position der Partei einordnen lassen, indem du auf den Knopf unter der Antwort klickst.',
  'Falls uns das Abstimmungsverhalten der Partei vorliegt, kannst du die Antwort auch mit passenden Gesetzesvorschlägen abgleichen.',
];

const ACCORDION_CONTENT = [
  {
    id: 'questions',
    title: 'Welche Fragen kann ich stellen?',
    content: {
      intro:
        'Grundsätzlich kannst du alle Fragen stellen, die du zu den Positionen der Parteien hast. Falls du mehrere Parteien miteinander vergleichen willst, kannst du sie entweder dem Chat hinzufügen oder sie einfach in der Frage erwähnen. Des Weiteren kannst du auch Fragen zu generellen Themen wie dem Ablauf einer Wahl stellen.',
      sections: [
        {
          subtitle: 'Beispiele für Partei-spezifische Fragen:',
          list: PARTY_SPECIFIC_QUESTIONS,
        },
        {
          subtitle: 'Beispiele für vergleichende Fragen:',
          list: COMPARE_QUESTIONS,
        },
        {
          subtitle: 'Beispiele für allgemeine Fragen:',
          list: GENERAL_QUESTIONS,
        },
      ],
    },
  },
  {
    id: 'elections-supported',
    title: 'Welche Wahlen werden unterstützt?',
    content: {
      intro: 'Aktuell unterstützen wir folgende Wahlen:',
      list: [
        'Landtagswahl Baden-Württemberg - 8. März 2026',
        'Landtagswahl Rheinland-Pfalz - 22. März 2026',
        'Kommunalwahl München - 8. März 2026',
      ],
      outro:
        'Zusätzlich können im Bereich **Bundesebene** allgemeine Informationen über die Positionen der Parteien beantwortet werden.',
    },
  },
  {
    id: 'number-parties',
    title: 'Mit wie vielen Parteien kann ich chatten?',
    content: {
      paragraphs: [
        `Du kannst den Chat mit bis zu ${MAX_SELECTABLE_PARTIES} Parteien gleichzeitig starten, hast aber die Möglichkeit, während des Chattens noch weitere Parteien anzusprechen.`,
        'Des Weiteren kannst du ganz einfach durch den Plus-Knopf über dem Textfeld weitere Parteien zum Chat hinzufügen oder auch wieder entfernen.',
      ],
    },
  },
  {
    id: 'position',
    title: 'Position einordnen',
    content: {
      paragraphs: [
        'Wenn du diesen Knopf unter einer der Nachrichten klickst, wird die Position der Nachricht eingeordnet. Dabei werden die folgenden Kriterien berücksichtigt: Machbarkeit, kurzfristige und langfristige Effekte.',
        'Hierbei nutzen wir aktuelle Informationen und Quellen aus dem Internet, die uns von Perplexity.ai zur Verfügung gestellt werden.',
      ],
    },
  },
  {
    id: 'voting-behavior-analyze',
    title: 'Abstimmungsverhalten analysieren',
    content: {
      paragraphs: [
        'Mit dieser Funktion kannst du die Antwort einer Partei im Kontext vergangener Abstimmungen im Bundestag einordnen. Darüber hinaus kannst du durch einen Klick auf "Abstimmungen anzeigen" detaillierte Informationen zu den relevanten Abstimmungen anzeigen und visualisieren lassen. Dies ermöglicht es, die Pläne einer Partei laut ihrem Programm anhand ihres realpolitischen Verhaltens einzuordnen.',
      ],
    },
  },
  {
    id: 'data',
    title: 'Welche Daten werden verwendet?',
    content: {
      intro:
        'Um fundierte und quellenbasierte Antworten zu liefern, verwendet wahl.chat eine Vielzahl von Datenquellen:',
      orderedList: [
        'Parteidokumente: Als Datenbasis werden Grundsatzprogramme, Wahlprogramme, Positionspapiere und weitere von den Parteien stammende Dokumente herangezogen, um ein umfassendes Bild der Parteipositionen zu erhalten.',
        'Abstimmungsverhalten im Bundestag: Für die Analyse des Abstimmungsverhaltens nutzen wir Daten zu Bundestagsabstimmungen, die über abgeordnetenwatch.de bereitgestellt werden. Diese Daten ermöglichen es, Parteipositionen mit ihrem realpolitischen Verhalten abzugleichen.',
        'Internetquellen für die Einordnung von Positionen: Für die differenzierte Einordnung von Positionen nutzt wahl.chat den Dienst Perplexity.ai, der hochwertige Internetquellen wie Nachrichtenseiten verwendet.',
      ],
      outro:
        'Wir haben alle Quellen, die wahl.chat nutzt, auf unserer Webseite unter /sources aufgelistet.',
    },
  },
  {
    id: 'guidelines',
    title: 'Welchen Leitlinien folgt wahl.chat in seinen Antworten?',
    content: {
      intro: 'Folgende Leitlinien gelten für die Antworten in den Chats:',
      orderedList: [
        'Quellenbasiert: Die Antworten sollen auf den relevanten Aussagen aus den bereitgestellten Programmauszügen beruhen.',
        'Neutralität: Parteipositionen sollen neutral und ohne Wertung wiedergegeben werden.',
        'Transparenz: Zu jeder Aussage sollen direkt die relevanten Quellen verlinkt werden, um eine detaillierte Betrachtung und Überprüfung des Inhalts zu ermöglichen.',
      ],
    },
  },
  {
    id: 'party-selection',
    title: 'Nach welchen Kriterien werden die Parteien ausgewählt?',
    content: {
      paragraphs: [
        'Die ursprüngliche Auswahl der Parteien für den bundesweiten Kontext erfolgte vor der Bundestagswahl 2025 und orientierte sich an der Veröffentlichung ihrer Wahlprogramme. Wir wollen nun nach und nach auch für die anderen unterstützten Wahlen eine möglichst vollständige Parteienauswahl anbieten und freuen uns dafür über deine Mithilfe.',
        'Solltest du eine Partei vermissen, schreibe uns gerne eine E-Mail mit ihrem Wahl- oder Grundsatzprogramm oder anderen relevanten Dokumenten als PDF an info@wahl.chat, und wir werden sie so schnell wie möglich ergänzen.',
      ],
    },
  },
  {
    id: 'about-founders',
    title: 'Wer steckt hinter wahl.chat und wie kam es dazu?',
    content: {
      intro:
        'Gegründet wurde wahl.chat von fünf Studierenden der LMU, TUM und University of Cambridge. Sie kamen für ein gemeinsames Forschungsprojekt zum Thema KI in Cambridge zusammen und haben mittlerweile ihre Studien abgeschlossen.',
      sections: [
        {
          subtitle: 'Die Gründungsmitglieder und ihre heutigen Positionen:',
          list: [
            'Sebastian Maier - Doktorand an der LMU München',
            'Anton Wyrowski - Entwickler bei Perplexity',
            'Michel Schimpf - Doktorand an der University of Cambridge',
            'Robin Frasch - Doktorand an der Uni Hamburg',
            'Roman Mayr - Entwickler bei Knowunity',
          ],
        },
      ],
      origin:
        'Ende November 2024 saß das Team in Cambridge beim Mittagessen zusammen. Beim Gespräch kam das Thema auf, dass der Opa des Deutschrappers Ski Aggu am Wahl-O-Mat gearbeitet hat. Es kam die Idee auf, einen neuen Wahl-O-Mat mit KI für die Einordnung der eigenen Meinung zu den Wahlkampfthemen zu bauen. Doch wäre es nicht noch spannender, den Spieß umzudrehen und mit den für einen selbst relevanten Parteien ausführlicher zu chatten? Und nicht nur eine Aussage zu vorgeschriebenen Thesen zu erhalten, sondern ganz individuelle Anliegen klären zu können? Und so war Ende November 2024 die Idee für wahl.chat geboren.',
      outro: 'Weitere Infos können auch unter /about-us nachgelesen werden.',
    },
  },
  {
    id: 'wahl-o-mat-difference',
    title: 'Wie unterscheidet sich wahl.chat vom Wahl-O-Mat?',
    content: {
      intro:
        'Beim Wahl-O-Mat entscheidet man zu vorgegebenen Thesen "finde ich gut", "hier bin ich neutral", oder "hier bin ich dagegen". wahl.chat ist dagegen wie ein offenes Gespräch, um besser zu verstehen, was die Parteien fordern.',
      orderedList: [
        'Fragen zu den Themen stellen, die einen selbst am meisten interessieren.',
        'Ins Detail gehen, um die Begriffe, Vorstellungen und Pläne der Parteien genau zu verstehen.',
        'Positionen kritisch einordnen, um Für- und Wider abzuwägen.',
      ],
    },
  },
  {
    id: 'data-privacy',
    title: 'Sind meine Daten bei der Verwendung von wahl.chat sicher?',
    content: {
      paragraphs: [
        'Ja, wahl.chat kommt ohne Cookies und ohne die Erfassung persönlicher Daten aus. Lediglich die Chats werden anonymisiert gespeichert. Durch Zugriffskontrollen verhindern wir unbefugten Zugriff auf die Chats anderer.',
        'Man sollte dennoch vermeiden, sensible persönliche Daten in die Chats zu schreiben.',
      ],
    },
  },
  {
    id: 'usage-statistics',
    title: 'Werden Nutzungsstatistiken erfasst?',
    content: {
      paragraphs: [
        'Um wahl.chat kontinuierlich zu verbessern, werden die Webseitenanfragen und die anonymisierten Chatverläufe verwendet, um aggregierte Statistiken, wie die Anzahl der beantworteten Fragen oder die Parteien, mit denen am meisten gechattet wird, zu bestimmen.',
        'Da wir die Entwicklung von wahl.chat wissenschaftlich begleiten, werden wir von Zeit zu Zeit unseren Nutzerinnen und Nutzern die Möglichkeit geben, an Studien teilzunehmen. Diese werden 100% freiwillig sein und eine Ablehnung wird keinen Einfluss auf die weitere Verwendbarkeit von wahl.chat haben. In diesen Studien werden wir die anonymisierten Nutzungsstatistiken verwenden, um die Wirkung von wahl.chat zu analysieren und den positiven Impact weiter zu verbessern.',
      ],
    },
  },
  {
    id: 'learning',
    title: 'Lernt wahl.chat mit der Zeit selbstständig dazu?',
    content: {
      paragraphs: [
        'Nein, die Chatverläufe werden nicht für weiteres Training der LLMs verwendet. Wir arbeiten allerdings kontinuierlich daran, die Qualität der Antworten zu verbessern, halten unsere Datenbasis stets aktuell und planen, weitere relevante Dokumente zur Antwortgenerierung hinzuzufügen.',
      ],
    },
  },
  {
    id: 'contribute',
    title: 'Wie kann ich zu wahl.chat beitragen?',
    content: {
      paragraphs: [
        'wahl.chat ist ein Open-Source-Projekt und unser Code ist öffentlich auf GitHub einsehbar unter https://github.com/wahl-chat.',
        'Wir freuen uns über Unterstützung und sind immer auf der Suche nach Freiwilligen, die mit uns gemeinsam die Demokratie stärken möchten. Wenn du Interesse hast, dich einzubringen, kontaktiere uns gerne unter info@wahl.chat.',
      ],
    },
  },
];

const PROCESS_STEP_ICONS = [
  <MessageCircleQuestionIcon key="icon1" className="absolute left-0 top-0" />,
  <TextSearchIcon key="icon2" className="absolute left-0 top-0" />,
  <MessageCircleReplyIcon key="icon3" className="absolute left-0 top-0" />,
  <WaypointsIcon key="icon4" className="absolute left-0 top-0" />,
];

function HowTo() {
  const [isExporting, setIsExporting] = useState(false);

  const buildQuestionLink = (question: string) => {
    return `/session?q=${question}`;
  };

  const exportToPDF = async () => {
    setIsExporting(true);
    try {
      await exportHowToPDF({
        introText: INTRO_TEXT,
        processSteps: PROCESS_STEPS,
        accordionContent: ACCORDION_CONTENT,
      });
    } catch (error) {
      console.error('Error generating PDF:', error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Accordion type="single" collapsible asChild>
      <article>
        <section>
          <p>
            <span className="font-bold underline">wahl.chat</span>{' '}
            {INTRO_TEXT.main.startsWith('wahl.chat ')
              ? INTRO_TEXT.main.slice('wahl.chat '.length)
              : INTRO_TEXT.main}
            <br />
            {INTRO_TEXT.sources}
          </p>

          <p className="mt-4 text-sm font-semibold">Der Prozess ist einfach:</p>

          <ul className="[&_li]:mt-4 [&_li]:text-sm">
            {PROCESS_STEPS.map((step, index) => (
              <li key={step} className="relative pl-10">
                {PROCESS_STEP_ICONS[index]}
                {step}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-6">
          {ACCORDION_CONTENT.map((accordionItem) => (
            <AccordionItem key={accordionItem.id} value={accordionItem.id}>
              <AccordionTrigger className="font-bold">
                {accordionItem.title}
              </AccordionTrigger>
              <AccordionContent>
                {/* Special rendering for questions accordion */}
                {accordionItem.id === 'questions' && (
                  <>
                    {accordionItem.content.intro}
                    <br />
                    <br />
                    {accordionItem.content.sections?.map((section) => (
                      <div key={section.subtitle}>
                        <span className="font-bold">{section.subtitle}</span>
                        <ul className="list-outside list-disc py-2 pl-4 [&_li]:pt-1">
                          {section.list?.map((question) => (
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
                      </div>
                    ))}
                  </>
                )}

                {/* Elections supported accordion */}
                {accordionItem.id === 'elections-supported' && (
                  <>
                    {accordionItem.content.intro}
                    <ul className="list-outside list-disc py-2 pl-4 [&_li]:pt-1">
                      {accordionItem.content.list?.map((item) => (
                        <li key={item}>
                          <span className="font-bold">{item}</span>
                        </li>
                      ))}
                    </ul>
                    <br />
                    {accordionItem.content.outro}
                  </>
                )}

                {/* Number of parties accordion */}
                {accordionItem.id === 'number-parties' && (
                  <>
                    {accordionItem.content.paragraphs?.[0]}
                    <br />
                    <br />
                    {(() => {
                      const text = accordionItem.content.paragraphs?.[1] || '';
                      const parts = text.split('Plus-Knopf');
                      return (
                        <>
                          {parts[0]}
                          <span className="inline-block">
                            <PlusIcon className="size-4 rounded-full bg-primary p-1 text-primary-foreground" />
                          </span>
                          -Knopf{parts[1]}
                        </>
                      );
                    })()}
                  </>
                )}

                {/* Position accordion */}
                {accordionItem.id === 'position' && (
                  <>
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
                    {accordionItem.content.paragraphs?.map((para, idx) => (
                      <p key={para}>
                        {para}
                        {idx <
                          (accordionItem.content.paragraphs?.length || 0) -
                            1 && <br />}
                      </p>
                    ))}
                  </>
                )}

                {/* Voting behavior accordion */}
                {accordionItem.id === 'voting-behavior-analyze' && (
                  <>
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
                    <p>{accordionItem.content.paragraphs?.[0]}</p>
                  </>
                )}

                {/* Data sources accordion */}
                {accordionItem.id === 'data' && (
                  <>
                    {(() => {
                      const intro = accordionItem.content.intro || '';
                      const introParts = intro.split('wahl.chat');
                      return (
                        <>
                          {introParts[0]}
                          <span className="font-bold underline">wahl.chat</span>
                          {introParts[1]}
                        </>
                      );
                    })()}
                    <ol className="list-outside list-decimal py-4 pl-4 [&_li]:pt-1">
                      {accordionItem.content.orderedList?.map((item) => {
                        const parts = item.split(':');
                        const isAbstimmungsverhalten = parts[0].includes(
                          'Abstimmungsverhalten',
                        );
                        return (
                          <li key={item}>
                            <div className="pl-2">
                              {isAbstimmungsverhalten ? (
                                <>
                                  <span className="font-bold">{parts[0]}:</span>{' '}
                                  {(() => {
                                    const text = parts.slice(1).join(':');
                                    const linkParts = text.split(
                                      'abgeordnetenwatch.de',
                                    );
                                    return (
                                      <>
                                        {linkParts[0]}
                                        <a
                                          href="https://www.abgeordnetenwatch.de"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="underline"
                                        >
                                          abgeordnetenwatch.de
                                        </a>
                                        {linkParts[1]}
                                      </>
                                    );
                                  })()}
                                </>
                              ) : (
                                <>
                                  <span className="font-bold">{parts[0]}:</span>{' '}
                                  {parts.slice(1).join(':')}
                                </>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ol>
                    <br />
                    {(() => {
                      const outro = accordionItem.content.outro || '';
                      const outroParts = outro.split('wahl.chat');
                      const beforeLink = outroParts[0];
                      const afterWahlChat = outroParts[1] || '';
                      const sourceParts = afterWahlChat.split('/sources');
                      return (
                        <>
                          {beforeLink}
                          <span className="font-bold underline">wahl.chat</span>
                          {sourceParts[0]}
                          <Link href="/sources" className="underline">
                            hier
                          </Link>
                          {sourceParts[1]?.replace(
                            ' aufgelistet.',
                            ' aufgelistet.',
                          )}
                        </>
                      );
                    })()}
                  </>
                )}

                {/* Guidelines accordion */}
                {accordionItem.id === 'guidelines' && (
                  <>
                    {accordionItem.content.intro}
                    <ol className="list-outside list-decimal py-4 pl-4 [&_li]:pt-1">
                      {accordionItem.content.orderedList?.map((item) => {
                        const parts = item.split(':');
                        return (
                          <li key={item}>
                            <div className="pl-2">
                              <span className="font-bold">{parts[0]}:</span>{' '}
                              {parts.slice(1).join(':')}
                            </div>
                          </li>
                        );
                      })}
                    </ol>
                  </>
                )}

                {/* Party selection accordion */}
                {accordionItem.id === 'party-selection' && (
                  <>
                    {accordionItem.content.paragraphs?.[0]}
                    <br />
                    <br />
                    {(() => {
                      const text = accordionItem.content.paragraphs?.[1] || '';
                      const parts = text.split('info@wahl.chat');
                      return (
                        <>
                          {parts[0]}
                          <a href="mailto:info@wahl.chat" className="underline">
                            info@wahl.chat
                          </a>
                          {parts[1]}
                        </>
                      );
                    })()}
                  </>
                )}

                {/* About founders accordion */}
                {accordionItem.id === 'about-founders' && (
                  <>
                    {accordionItem.content.intro}
                    <br />
                    <br />
                    {accordionItem.content.sections?.map((section) => (
                      <div key={section.subtitle}>
                        <span className="font-bold">{section.subtitle}</span>
                        <ul className="list-outside list-disc py-2 pl-4 [&_li]:pt-1">
                          {section.list?.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                        <br />
                      </div>
                    ))}
                    <span className="font-bold">Wie kam es zu wahl.chat?</span>
                    <br />
                    <br />
                    {accordionItem.content.origin}
                    <br />
                    <br />
                    {(() => {
                      const outro = accordionItem.content.outro || '';
                      const parts = outro.split('/about-us');
                      return (
                        <>
                          {parts[0]}
                          <Link href="/about-us" className="underline">
                            /about-us
                          </Link>
                          {parts[1]}
                        </>
                      );
                    })()}
                  </>
                )}

                {/* Wahl-O-Mat difference accordion */}
                {accordionItem.id === 'wahl-o-mat-difference' && (
                  <>
                    {accordionItem.content.intro}
                    <br />
                    <br />
                    <span className="font-bold">Bei wahl.chat kann man:</span>
                    <ol className="list-outside list-decimal py-2 pl-4 [&_li]:pt-1">
                      {accordionItem.content.orderedList?.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ol>
                  </>
                )}

                {/* Data privacy accordion */}
                {accordionItem.id === 'data-privacy' &&
                  accordionItem.content.paragraphs?.map((para, idx) => (
                    <p key={para}>
                      {para}
                      {idx <
                        (accordionItem.content.paragraphs?.length || 0) - 1 && (
                        <>
                          <br />
                          <br />
                        </>
                      )}
                    </p>
                  ))}

                {/* Usage statistics accordion */}
                {accordionItem.id === 'usage-statistics' &&
                  accordionItem.content.paragraphs?.map((para, idx) => (
                    <p key={para}>
                      {para}
                      {idx <
                        (accordionItem.content.paragraphs?.length || 0) - 1 && (
                        <>
                          <br />
                          <br />
                        </>
                      )}
                    </p>
                  ))}

                {/* Learning accordion */}
                {accordionItem.id === 'learning' && (
                  <p>{accordionItem.content.paragraphs?.[0]}</p>
                )}

                {/* Contribute accordion */}
                {accordionItem.id === 'contribute' && (
                  <>
                    {(() => {
                      const text = accordionItem.content.paragraphs?.[0] || '';
                      const parts = text.split('https://github.com/wahl-chat');
                      return (
                        <p>
                          {parts[0]}
                          <a
                            href="https://github.com/wahl-chat"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="underline"
                          >
                            https://github.com/wahl-chat
                          </a>
                          {parts[1]}
                        </p>
                      );
                    })()}
                    <br />
                    {(() => {
                      const text = accordionItem.content.paragraphs?.[1] || '';
                      const parts = text.split('info@wahl.chat');
                      return (
                        <p>
                          {parts[0]}
                          <a href="mailto:info@wahl.chat" className="underline">
                            info@wahl.chat
                          </a>
                          {parts[1]}
                        </p>
                      );
                    })()}
                  </>
                )}
              </AccordionContent>
            </AccordionItem>
          ))}
        </section>

        <div className="mt-8 flex justify-center">
          <Button
            onClick={exportToPDF}
            disabled={isExporting}
            variant="default"
            size="lg"
          >
            <DownloadIcon />
            {isExporting ? 'Erstelle PDF...' : 'Als PDF exportieren'}
          </Button>
        </div>
      </article>
    </Accordion>
  );
}

export default HowTo;
