'use client';

import { MessageCitationsList } from '@/modules/guided-exploration/components/shared/message-citations-list';
import { chatMessageHeadingId } from '@/modules/guided-exploration/components/shared/message-nav-links';
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type { SessionMessage } from '@/modules/guided-exploration/types';
import { useCitationHandlers } from '@/modules/guided-exploration/utils';

import { ExplorationTreeCard } from './exploration-tree-card';
import { TopicDirectionsCard } from './topic-directions-card';

/**
 * Distils a message body into a short, speakable string for the per-message
 * heading: strips party section/badge markers, citation tokens, markdown links
 * and syntax, then collapses whitespace. Keeps headings meaningful for
 * heading-rotor navigation instead of five identical "Antwort der KI".
 */
export function toPlainText(markdown: string): string {
  return markdown
    .replace(/!?\[([^\]]+)\]\([^)]*\)/g, '$1') // [text](url)/![alt](url) -> text
    .replace(
      /\[PARTY_BADGE:([\w-]+)\]/g,
      (_, id: string) => id.charAt(0).toUpperCase() + id.slice(1).toLowerCase(),
    ) // inline party badge -> capitalised party id (stripping it is confusing)
    .replace(/\[\/?PARTY:[\w-]+\]/g, ' ') // party section open/close markers
    .replace(/\[[\w.-]+(?:\s*,\s*[\w.-]+)*\]/g, ' ') // citation tokens [id]/[id, id]
    .replace(/^\s*[#>\-*+]+\s*/gm, '') // line-start heading/quote/list markers
    .replace(/[*_`~]+/g, '') // emphasis / code fences
    .replace(/<[^>]+>/g, ' ') // stray html (e.g. <br>)
    .replace(/\s+/g, ' ')
    .trim();
}

/** First sentence of `text`, capped at `maxLen` chars on a word boundary. */
function buildSnippet(text: string, maxLen = 100): string {
  if (!text) return '';
  const sentence = text.match(/^.*?[.!?](?=\s|$)/)?.[0] ?? text;
  if (sentence.length <= maxLen) return sentence;
  const cut = sentence.slice(0, maxLen);
  const lastSpace = cut.lastIndexOf(' ');
  return `${(lastSpace > 40 ? cut.slice(0, lastSpace) : cut).trim()}…`;
}

/**
 * Plain-text first sentence of a message body, for live-region narration.
 * Strips markdown/citation/party markers first so the announcer speaks clean
 * prose rather than syntax.
 */
export function firstSentence(markdown: string, maxLen = 160): string {
  return buildSnippet(toPlainText(markdown), maxLen);
}

/** Content-bearing accessible name for a message's sr-only heading. */
function getMessageHeadingLabel(message: SessionMessage): string {
  switch (message.type) {
    case 'user': {
      const snippet = buildSnippet(toPlainText(message.content ?? ''));
      return snippet ? `Du: ${snippet}` : 'Deine Nachricht';
    }
    case 'assistant': {
      const snippet = buildSnippet(toPlainText(message.content ?? ''));
      return snippet ? `KI: ${snippet}` : 'Antwort der KI';
    }
    case 'exploration_start': {
      // Heading should say *what this is* (a structured topic exploration), not
      // echo the full query. Drop the "— Fokus: …" detail and keep just the
      // bare topic so first-time SR users understand the block they've reached.
      const raw = message.explorationQuery
        ? toPlainText(message.explorationQuery)
        : '';
      const topic = buildSnippet(raw.split('—')[0]?.trim() ?? '', 80);
      return topic
        ? `Strukturierte Erkundung zum Thema „${topic}“. Lies weiter für einen Überblick und die Unterthemen.`
        : 'Strukturierte Erkundung. Lies weiter für einen Überblick und die Unterthemen.';
    }
    case 'topic_directions':
      // Once the user has submitted, the card collapses to an inline summary —
      // the heading should match it ("Erkundet wird: …") rather than keep
      // prompting for a selection that's already been made.
      if (message.selectedDirections && message.selectedDirections.length > 0) {
        return `Erkundet wird: ${message.selectedDirections.join(' · ')}`;
      }
      return 'Aspekt-Auswahl: Wähle aus, welche Aspekte des Themas du genauer erkunden möchtest.';
    case 'choice_result':
      // content already reads e.g. "Strukturierte Erkundung ausgewählt."
      return message.content ?? 'Auswahl getroffen.';
  }
}

interface SessionMessageListProps {
  messages: SessionMessage[];
  onOpenLeafAction?: (explorationId: string, leafId: string) => void;
  onDirectionChoiceAction?: (
    queryId: string,
    directions: Array<{ id: string; name: string }>,
  ) => void;
  isLoading?: boolean;
  lastUserMessageIndex?: number;
  /**
   * Ref to the most recent user message's wrapper. The chat view focuses the
   * heading inside it on send (a managed focus move) so focus isn't dropped to
   * <body> when the composer disables.
   */
  lastUserMessageRef?: React.RefObject<HTMLDivElement | null>;
  /** Index of the most recent non-user message (assistant/exploration/directions). */
  lastBotMessageIndex?: number;
  /**
   * Ref to the most recent bot message's wrapper. The chat view focuses the
   * heading inside it once an answer settles so the user lands at the top of
   * the new reply.
   */
  lastBotMessageRef?: React.RefObject<HTMLDivElement | null>;
  /** Minimum number of directions the user must select */
  minDirections?: number;
  /** Owning tree of the deep-link leaf, used to scope `deepLinkLeafId`. */
  deepLinkExplorationId?: string | null;
  /** Leaf id from a `?leaf=<id>` deep link, forwarded to the matching card. */
  deepLinkLeafId?: string | null;
}

/**
 * The conversation transcript: a stack of messages, each a content-bearing
 * sr-only <h2>. The headings are the navigation model — screen-reader users
 * jump message-to-message via the heading rotor, while the enclosing
 * "Gesprächsverlauf" landmark gets them to the region. No list/article wrapper:
 * those duplicated the heading's name and added "list"/"article" verbosity.
 *
 * Purely structural — no live region, no focus effect. Narration lives in the
 * chat view's single status region; the managed focus moves (to the latest user
 * message on send, and the latest bot message on settle) are driven from the
 * chat view via `lastUserMessageRef`/`lastBotMessageRef`.
 */
export function SessionMessageList({
  messages,
  onOpenLeafAction,
  onDirectionChoiceAction,
  isLoading = false,
  lastUserMessageIndex = -1,
  lastUserMessageRef,
  lastBotMessageIndex = -1,
  lastBotMessageRef,
  minDirections,
  deepLinkExplorationId,
  deepLinkLeafId,
}: SessionMessageListProps) {
  return (
    <div className="space-y-4">
      {messages.map((message, index) => {
        const isLastUser = index === lastUserMessageIndex;
        const isLastBot = index === lastBotMessageIndex;

        let body: React.ReactNode = null;

        if (message.type === 'user') {
          body = (
            <div className="flex justify-end">
              <div className="max-w-[80%] rounded-[20px] bg-muted px-4 py-2">
                <p className="text-sm">{message.content}</p>
              </div>
            </div>
          );
        } else if (message.type === 'choice_result') {
          // Transient confirmation of the user's choice — a quiet inline note,
          // not a chat bubble. The sr-only heading above carries the same text
          // and is the focus target the chat view moves to on submit.
          body = (
            <p className="text-sm text-muted-foreground">{message.content}</p>
          );
        } else if (message.type === 'assistant') {
          body = <AssistantSessionMessage message={message} />;
        } else if (message.type === 'exploration_start') {
          const ownsDeepLink =
            !!deepLinkLeafId &&
            !!deepLinkExplorationId &&
            message.explorationId === deepLinkExplorationId;
          body = (
            <ExplorationTreeCard
              message={message}
              onOpenLeaf={onOpenLeafAction}
              deepLinkLeafId={ownsDeepLink ? deepLinkLeafId : null}
            />
          );
        } else if (message.type === 'topic_directions' && message.directions) {
          body = (
            <TopicDirectionsCard
              directions={{
                type: 'topic_directions',
                queryId: message.directionsQueryId ?? '',
                originalQuery: '',
                directions: message.directions,
              }}
              onSelectDirections={(directions) =>
                onDirectionChoiceAction?.(
                  message.directionsQueryId ?? '',
                  directions,
                )
              }
              isLoading={isLoading || !onDirectionChoiceAction}
              selectedDirections={message.selectedDirections}
              minSelections={minDirections}
            />
          );
        }

        if (!body) return null;

        return (
          <div
            key={message.id}
            ref={
              isLastUser
                ? lastUserMessageRef
                : isLastBot
                  ? lastBotMessageRef
                  : undefined
            }
          >
            {/* sr-only heading: content-bearing rotor anchor for jumping
                message-to-message, and the managed focus target. On send the
                chat view focuses the latest user message's heading; on settle
                it focuses the latest bot message's heading ([data-answer-start])
                so the user lands on "KI: …" / "Aspekt-Auswahl" — a heading,
                announced as "Überschrift" in every browser (never "group"). */}
            <h2
              id={chatMessageHeadingId(message.id)}
              className="sr-only outline-none"
              data-answer-start={isLastBot ? '' : undefined}
              tabIndex={-1}
            >
              {getMessageHeadingLabel(message)}
            </h2>
            {body}
          </div>
        );
      })}
    </div>
  );
}

function AssistantSessionMessage({
  message,
}: {
  message: SessionMessage;
}) {
  const citations = message.citations ?? [];
  const { getReferenceName, getReferenceTooltip, handleReferenceClick } =
    useCitationHandlers(citations);

  return (
    <div>
      <PartyMarkedMarkdown
        onReferenceClick={handleReferenceClick}
        getReferenceName={getReferenceName}
        getReferenceTooltip={getReferenceTooltip}
        baseHeadingLevel={2}
      >
        {message.content ?? ''}
      </PartyMarkedMarkdown>
      <MessageCitationsList citations={citations} messageId={message.id} />
    </div>
  );
}
