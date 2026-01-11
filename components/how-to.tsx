'use client';

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

// Type declaration for jsPDF
type JsPDFConstructor = new (options?: {
  orientation?: 'portrait' | 'landscape';
  unit?: string;
  format?: string;
}) => {
  internal: {
    pageSize: {
      getWidth: () => number;
      getHeight: () => number;
    };
  };
  setFontSize: (size: number) => void;
  setFont: (font: string, style: string) => void;
  splitTextToSize: (text: string, maxWidth: number) => string[];
  text: (text: string, x: number, y: number) => void;
  getTextWidth: (text: string) => number;
  line: (x1: number, y1: number, x2: number, y2: number) => void;
  addPage: () => void;
  save: (filename: string) => void;
};

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
  'Du kannst dir nun die Position der Partei einordnen lassen indem du auf den Knopf unter der Antwort klickst. Zusätzlich kannst du die Antwort auf Basis des Abstimmungsverhaltens der Partei analysieren lassen, sofern uns diese Informationen bei der jeweiligen Wahl zur Verfügung standen.',
];

const ACCORDION_CONTENT = [
  {
    id: 'questions',
    title: 'Welche Fragen kann ich stellen?',
    content: {
      intro:
        'Grundsätzlich kannst du alle Fragen stellen, die du zu den Positionen der Parteien hast. Falls du mehrere Parteien miteinander vergleichen willst, kannst sie entweder dem Chat hinzufügen oder sie einfach in der Frage erwähnen. Desweiteren kannst du auch Fragen zu generellen Themen wie dem Ablauf einer Wahl stellen.',
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
        'Zusätzlich bieten wir einen bundesweiten Kontext an, der allgemeine Informationen über die Parteien auf Bundesebene enthält.',
    },
  },
  {
    id: 'number-parties',
    title: 'Mit wie vielen Parteien kann ich chatten?',
    content: {
      paragraphs: [
        `Du kannst den Chat mit bis zu ${MAX_SELECTABLE_PARTIES} Parteien gleichzeitig starten, hast aber die Möglichkeit während des chattens noch weitere Parteien anzusprechen.`,
        'Desweiteren, kannst du ganz einfach durch den Plus-Knopf über dem Textfeld weitere Parteien zum Chat hinzufügen, oder auch wieder entfernen.',
      ],
    },
  },
  {
    id: 'position',
    title: 'Position Einordnen',
    content: {
      paragraphs: [
        'Wenn du diesen Knopf unter einer der Nachrichten klickst, wird die Position der Nachricht eingeordnet. Dabei werden die folgenden Kriterien berücksichtigt: Machbarkeit, Kurzfristige und Langfristige Effekte.',
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
        'Wir haben alle Quellen die wahl.chat nutzt auf unserer Webseite unter /sources aufgelistet.',
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
        'Die ursprüngliche Auswahl der Parteien für den bundesweiten Kontext erfolgte vor der Bundestagswahl 2025 und orientierte sich an der Veröffentlichung ihrer Wahlprogramme. Wir wollen nun nach und nach auch für die anderen unterstützen Wahlen eine möglichst vollständige Parteienauswahl anbieten und freuen uns dafür über deine Mithilfe.',
        'Solltest du eine Partei vermissen, schreibe uns gerne eine E-Mail mit ihrem Grundsatzprogramm als PDF im Anhang an info@wahl.chat, und wir werden sie so schnell wie möglich ergänzen.',
      ],
    },
  },
];

function HowTo() {
  const [isExporting, setIsExporting] = useState(false);

  const buildQuestionLink = (question: string) => {
    return `/session?q=${question}`;
  };

  const exportToPDF = async () => {
    setIsExporting(true);
    try {
      // Dynamic import to avoid SSR issues
      const jsPDFModule = (await import('jspdf')) as {
        default: JsPDFConstructor;
      };
      const jsPDF = jsPDFModule.default;

      const doc = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
      });

      const pageWidth = doc.internal.pageSize.getWidth();
      const pageHeight = doc.internal.pageSize.getHeight();
      const margin = 15;
      const maxWidth = pageWidth - 2 * margin;
      let yPosition = margin;

      // Helper function to add text with word wrapping
      const addText = (
        text: string,
        fontSize: number,
        isBold = false,
        isUnderline = false,
      ) => {
        if (yPosition > pageHeight - margin) {
          doc.addPage();
          yPosition = margin;
        }

        doc.setFontSize(fontSize);
        doc.setFont('helvetica', isBold ? 'bold' : 'normal');

        const lines = doc.splitTextToSize(text, maxWidth);
        for (const line of lines) {
          if (yPosition > pageHeight - margin) {
            doc.addPage();
            yPosition = margin;
          }
          doc.text(line, margin, yPosition);
          if (isUnderline) {
            const textWidth = doc.getTextWidth(line);
            doc.line(
              margin,
              yPosition + 0.5,
              margin + textWidth,
              yPosition + 0.5,
            );
          }
          yPosition += fontSize * 0.5;
        }
        yPosition += 3;
      };

      // Title
      addText('wahl.chat - Anleitung', 18, true, true);
      yPosition += 5;

      // Introduction
      addText(INTRO_TEXT.main, 11);
      addText(INTRO_TEXT.sources, 11);
      yPosition += 3;

      // Process steps
      addText('Der Prozess ist einfach:', 12, true);
      PROCESS_STEPS.forEach((step, index) => {
        addText(`${index + 1}. ${step}`, 11);
      });
      yPosition += 5;

      // Accordion content
      ACCORDION_CONTENT.forEach((section) => {
        addText(section.title, 14, true);

        const { content } = section;

        if (content.intro) {
          addText(content.intro, 11);
          if (content.list || content.orderedList || content.sections) {
            yPosition += 2;
          }
        }

        if (content.paragraphs) {
          content.paragraphs.forEach((para) => {
            addText(para, 11);
            yPosition += 2;
          });
        }

        if (content.list) {
          content.list.forEach((item) => {
            addText(`• ${item}`, 11);
          });
          yPosition += 2;
        }

        if (content.orderedList) {
          content.orderedList.forEach((item, index) => {
            addText(`${index + 1}. ${item}`, 11);
            yPosition += 2;
          });
        }

        if (content.sections) {
          content.sections.forEach((subsection) => {
            if (subsection.subtitle) {
              addText(subsection.subtitle, 11, true);
            }
            if (subsection.list) {
              subsection.list.forEach((item) => {
                addText(`• ${item}`, 10);
              });
              yPosition += 2;
            }
          });
        }

        if (content.outro) {
          addText(content.outro, 11);
        }

        yPosition += 5;
      });

      // Save the PDF
      doc.save('wahl-chat-anleitung.pdf');
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
            {PROCESS_STEPS.map((step, index) => {
              const icons = [
                <MessageCircleQuestionIcon
                  key="icon1"
                  className="absolute left-0 top-0"
                />,
                <TextSearchIcon
                  key="icon2"
                  className="absolute left-0 top-0"
                />,
                <MessageCircleReplyIcon
                  key="icon3"
                  className="absolute left-0 top-0"
                />,
                <WaypointsIcon key="icon4" className="absolute left-0 top-0" />,
              ];
              return (
                <li key={step} className="relative pl-10">
                  {icons[index]}
                  {step}
                </li>
              );
            })}
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
                    Desweiteren, kannst du ganz einfach durch den{' '}
                    <span className="inline-block">
                      <PlusIcon className="size-4 rounded-full bg-primary p-1 text-primary-foreground" />
                    </span>{' '}
                    knopf über dem Textfeld weitere Parteien zum Chat
                    hinzufügen, oder auch wieder entfernen.
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
                    Um fundierte und quellenbasierte Antworten zu liefern,
                    verwendet{' '}
                    <span className="font-bold underline">wahl.chat</span> eine
                    Vielzahl von Datenquellen:
                    <ol className="list-outside list-decimal py-4 pl-4 [&_li]:pt-1">
                      {accordionItem.content.orderedList?.map((item, idx) => {
                        const parts = item.split(':');
                        return (
                          <li key={item}>
                            <div className="pl-2">
                              {idx === 1 ? (
                                <>
                                  <span className="font-bold">{parts[0]}:</span>{' '}
                                  Für die Analyse des Abstimmungsverhaltens
                                  nutzen wir Daten zu Bundestagsabstimmungen,
                                  die über{' '}
                                  <a
                                    href="https://www.abgeordnetenwatch.de"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="underline"
                                  >
                                    abgeordnetenwatch.de
                                  </a>{' '}
                                  bereitgestellt werden. Diese Daten ermöglichen
                                  es, Parteipositionen mit ihrem realpolitischen
                                  Verhalten abzugleichen.
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
                    Wir haben alle Quellen die{' '}
                    <span className="font-bold underline">wahl.chat</span> nutzt{' '}
                    <Link href="/sources" className="underline">
                      hier
                    </Link>{' '}
                    aufgelistet.
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
                    Solltest du eine Partei vermissen, schreibe uns gerne eine
                    E-Mail mit ihrem Grundsatzprogramm als PDF im Anhang an{' '}
                    <a href="mailto:info@wahl.chat" className="underline">
                      info@wahl.chat
                    </a>
                    , und wir werden sie so schnell wie möglich ergänzen.
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
