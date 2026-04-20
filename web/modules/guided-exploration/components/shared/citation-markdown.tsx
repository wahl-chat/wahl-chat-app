'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import type { DetailedHTMLProps, HTMLAttributes, JSX } from 'react';
import { createElement, memo } from 'react';
import type { Components } from 'react-markdown';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PartyBadge } from './party-badge';

interface CitationMarkdownProps {
  children: string;
  /** Callback when a citation reference is clicked */
  onReferenceClick: (id: string) => void;
  /** Get display name for a citation ID */
  getReferenceName?: (id: string) => string | null;
  /** Get tooltip text for a citation ID */
  getReferenceTooltip?: (id: string) => string | null;
}

// Combined splitter for inline tokens we want to extract from text:
//   - citations:    [id]  or  [id1, id2]
//   - party badges: [PARTY_BADGE:id]
const INLINE_TOKEN_REGEX =
  /(\[PARTY_BADGE:[\w-]+\]|\[[\w.-]+(?:\s*,\s*[\w.-]+)*\])/g;
const CITATION_MATCH = /^\[([\w.-]+(?:\s*,\s*[\w.-]+)*)\]$/;
const PARTY_BADGE_MATCH = /^\[PARTY_BADGE:([\w-]+)\]$/;

/**
 * Renders a citation reference button with tooltip
 */
function CitationReference({
  ids,
  index,
  onReferenceClick,
  getReferenceTooltip,
  getReferenceName,
}: {
  ids: string[];
  index: number;
  onReferenceClick: (id: string) => void;
  getReferenceTooltip?: (id: string) => string | null;
  getReferenceName?: (id: string) => string | null;
}) {
  // Hidden from SR + keyboard: inline "Quelle 1" announcements mid-sentence
  // would shred reading flow. The canonical a11y affordance is the sources
  // list rendered separately (see InitialContentMessage); these inline chips
  // are a mouse-only convenience jumper.
  return (
    <span
      key={index}
      className="inline-flex flex-row flex-wrap gap-1"
      aria-hidden="true"
    >
      {ids.map((id) => {
        const name = getReferenceName?.(id) ?? `[${id}]`;
        const tooltip = getReferenceTooltip?.(id) ?? name;

        return (
          <Tooltip key={id}>
            <TooltipTrigger asChild>
              <button
                type="button"
                tabIndex={-1}
                className={cn(
                  'inline-flex cursor-pointer items-center justify-center rounded-full bg-muted px-2 py-1 text-xs transition-colors hover:bg-muted/80',
                )}
                onClick={() => onReferenceClick(id)}
              >
                {name}
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-96 text-ellipsis whitespace-nowrap">
              {tooltip}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </span>
  );
}

const NonMemoizedCitationMarkdown = ({
  children,
  onReferenceClick,
  getReferenceTooltip,
  getReferenceName,
}: CitationMarkdownProps) => {
  const cleanProps = (props: Record<string, unknown>) => {
    const rest = { ...props };
    rest.node = undefined;
    return rest;
  };

  function checkAndBuildReference(
    tag: keyof JSX.IntrinsicElements,
    {
      children,
      ...props
    }: DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>,
  ) {
    const buildReference = (children: string) => {
      // Splits text on both citation tokens ([id], [id1, id2]) and party
      // badge tokens ([PARTY_BADGE:id]). Citation IDs may contain word chars,
      // dots, or hyphens (e.g. [oedp-soziale_gerechtigkeit.sozialpolitik-148daf66]).
      const parts = children.split(INLINE_TOKEN_REGEX);

      if (parts.length > 1) {
        return parts.map((part, index) => {
          const badgeMatch = part.match(PARTY_BADGE_MATCH);
          if (badgeMatch) {
            return (
              <PartyBadge
                key={`badge-${index}-${badgeMatch[1]}`}
                party={badgeMatch[1]}
                inline
              />
            );
          }

          const citationMatch = part.match(CITATION_MATCH);
          if (citationMatch) {
            // Dedupe IDs so `[foo, foo]` doesn't render two identically-keyed
            // children in the CitationReference list.
            const ids = Array.from(new Set(citationMatch[1].split(/\s*,\s*/)));
            return (
              <CitationReference
                key={`${index}-${ids.join('-')}`}
                ids={ids}
                index={index}
                onReferenceClick={onReferenceClick}
                getReferenceTooltip={getReferenceTooltip}
                getReferenceName={getReferenceName}
              />
            );
          }
          return part;
        });
      }

      return children;
    };

    if (typeof children === 'string') {
      return createElement(tag, props, buildReference(children));
    }

    if (Array.isArray(children)) {
      return createElement(
        tag,
        props,
        children.map((child) => {
          if (typeof child === 'string') {
            return buildReference(child);
          }
          return child;
        }),
      );
    }

    return createElement(tag, props, children);
  }

  const components: Partial<Components> = {
    code: (props) => {
      const { className, children, ...rest } = props;
      const { inline, ...restWithoutInline } = rest as Record<string, unknown>;
      const match = /language-(\w+)/.exec(className || '');
      const cleaned = cleanProps(restWithoutInline);

      return !inline && match ? (
        <pre
          className={`${className} mt-2 w-full overflow-x-scroll rounded-lg bg-zinc-100 p-3 text-sm dark:bg-zinc-800`}
          {...cleaned}
        >
          <code className={match[1]}>{children}</code>
        </pre>
      ) : (
        <code
          className={`${className} rounded-md bg-zinc-100 px-1 py-0.5 text-sm dark:bg-zinc-800`}
          {...cleaned}
        >
          {children}
        </code>
      );
    },
    ol: ({ children, ...props }) => {
      return (
        <ol className="ml-4 list-outside list-decimal" {...cleanProps(props)}>
          {children}
        </ol>
      );
    },
    li: ({ children, ...props }) => {
      return checkAndBuildReference('li', {
        children,
        className: 'py-1',
        ...cleanProps(props),
      });
    },
    ul: ({ children, ...props }) => {
      return (
        <ul className="ml-4 list-outside list-disc" {...cleanProps(props)}>
          {children}
        </ul>
      );
    },
    strong: ({ children, ...props }) => {
      return (
        <span className="font-semibold" {...cleanProps(props)}>
          {children}
        </span>
      );
    },
    em: ({ children, ...props }) => {
      return checkAndBuildReference('em', { children, ...cleanProps(props) });
    },
    p: ({ children, ...props }) => {
      return checkAndBuildReference('p', { children, ...cleanProps(props) });
    },
    a: ({ children, href, ...props }) => {
      if (!href) {
        return (
          <span
            className="text-blue-500 hover:underline"
            {...cleanProps(props)}
          >
            {children}
          </span>
        );
      }
      return (
        <Link
          href={href}
          className="text-blue-500 hover:underline"
          target="_blank"
          rel="noreferrer"
          {...cleanProps(props)}
        >
          {children}
        </Link>
      );
    },
    h1: ({ children, ...props }) => (
      <h1 className="my-0 text-2xl font-bold" {...cleanProps(props)}>
        {children}
      </h1>
    ),
    h2: ({ children, ...props }) => (
      <h2 className="my-0 text-xl font-semibold" {...cleanProps(props)}>
        {children}
      </h2>
    ),
    h3: ({ children, ...props }) => (
      <h3 className="my-0 text-lg font-semibold" {...cleanProps(props)}>
        {children}
      </h3>
    ),
    h4: ({ children, ...props }) => (
      <h4 className="my-0 text-base font-semibold" {...cleanProps(props)}>
        {children}
      </h4>
    ),
  };

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {children}
    </ReactMarkdown>
  );
};

export const CitationMarkdown = memo(
  NonMemoizedCitationMarkdown,
  (prevProps, nextProps) => prevProps.children === nextProps.children,
);
