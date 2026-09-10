'use client';

import {
  ACCORDION_CONTENT,
  INTRO_TEXT,
  PROCESS_STEPS,
  WAHL_O_MAT_LIST_LEAD_IN,
  parseLabeledListItem,
  splitOnSourceDomains,
} from '@/lib/how-to-content';
import { exportHowToPDF } from '@/lib/how-to-pdf-export';
import { DownloadIcon, PlusIcon, VoteIcon } from 'lucide-react';
import Link from 'next/link';
import { Fragment, useState } from 'react';
import ChatActionButtonHighlight from './chat/chat-action-button-highlight';
import ProConIcon from './chat/pro-con-icon';
import HowToIntro from './how-to-intro';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './ui/accordion';
import { Button } from './ui/button';

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
          <HowToIntro />
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
                        const { label, text } = parseLabeledListItem(item);
                        return (
                          <li key={item}>
                            <div className="pl-2">
                              <span className="font-bold">{label}:</span>{' '}
                              {splitOnSourceDomains(text).map((segment) =>
                                segment.href ? (
                                  <a
                                    key={segment.text}
                                    href={segment.href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="underline"
                                  >
                                    {segment.text}
                                  </a>
                                ) : (
                                  <Fragment key={segment.text}>
                                    {segment.text}
                                  </Fragment>
                                ),
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
                        const { label, text } = parseLabeledListItem(item);
                        return (
                          <li key={item}>
                            <div className="pl-2">
                              <span className="font-bold">{label}:</span> {text}
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
                    <span className="font-bold">{WAHL_O_MAT_LIST_LEAD_IN}</span>
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
