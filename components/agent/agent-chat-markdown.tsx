'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { Source } from '@/lib/stores/chat-store.types';
import { buildPdfUrl } from '@/lib/utils';
import Link from 'next/link';
import { type JSX, memo, useMemo } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

type Props = {
  content: string;
  sources?: Source[];
};

// Reference key format: "party_id:index"
type ReferenceKey = string;

type ReferenceMapping = {
  displayNumber: number; // 1-indexed global display number
  source: Source | null;
};

// Regex to match [party_id][N] or [party_id][N, M, ...] format
// e.g., [spd][0], [cdu][1], [spd][0, 1], [cdu][0,1,2]
const REFERENCE_PATTERN = /\[([a-z]+)]\[(\d+(?:,\s*\d+)*)]/g;

// Group sources by party_id for lookup
function groupSourcesByParty(sources: Source[]): Map<string, Source[]> {
  const grouped = new Map<string, Source[]>();
  for (const source of sources) {
    if (!source.party_id) continue;
    const existing = grouped.get(source.party_id) || [];
    existing.push(source);
    grouped.set(source.party_id, existing);
  }
  return grouped;
}

// Parse comma-separated indices from a match, e.g., "0, 1" -> [0, 1]
function parseIndices(indicesStr: string): number[] {
  return indicesStr.split(',').map((s) => Number.parseInt(s.trim(), 10));
}

// Build a mapping from reference keys to global display numbers (in order of appearance)
function buildReferenceMapping(
  content: string,
  sourcesByParty: Map<string, Source[]>,
): Map<ReferenceKey, ReferenceMapping> {
  const mapping = new Map<ReferenceKey, ReferenceMapping>();
  const matches = Array.from(content.matchAll(REFERENCE_PATTERN));

  let displayNumber = 1;
  for (const match of matches) {
    const partyId = match[1];
    const indices = parseIndices(match[2]);

    for (const partyIndex of indices) {
      const key: ReferenceKey = `${partyId}:${partyIndex}`;

      // Only add if not already seen (first occurrence determines the number)
      if (!mapping.has(key)) {
        const partySources = sourcesByParty.get(partyId);
        const source = partySources?.[partyIndex] ?? null;

        mapping.set(key, {
          displayNumber: displayNumber++,
          source,
        });
      }
    }
  }

  return mapping;
}

function AgentChatMarkdownComponent({ content, sources }: Props) {
  const hasSources = sources && sources.length > 0;

  const sourcesByParty = useMemo(
    () => (hasSources ? groupSourcesByParty(sources) : new Map()),
    [sources, hasSources],
  );

  const referenceMapping = useMemo(
    () =>
      hasSources ? buildReferenceMapping(content, sourcesByParty) : new Map(),
    [content, sourcesByParty, hasSources],
  );

  const onReferenceClick = (partyId: string, partyIndex: number) => {
    const key: ReferenceKey = `${partyId}:${partyIndex}`;
    const mapping = referenceMapping.get(key);
    const source = mapping?.source;

    if (!source) return;

    const isPdfLink = source.url?.includes('.pdf');
    if (isPdfLink) {
      const url = buildPdfUrl(source);
      window.open(url.toString(), '_blank');
    } else if (source.url) {
      window.open(source.url, '_blank');
    }
  };

  const getReferenceTooltip = (
    partyId: string,
    partyIndex: number,
  ): string | null => {
    const key: ReferenceKey = `${partyId}:${partyIndex}`;
    const mapping = referenceMapping.get(key);
    const source = mapping?.source;

    if (!source) return null;
    return `${source.source} - Seite: ${source.page}`;
  };

  const getDisplayNumber = (partyId: string, partyIndex: number): number => {
    const key: ReferenceKey = `${partyId}:${partyIndex}`;
    const mapping = referenceMapping.get(key);
    return mapping?.displayNumber ?? 0;
  };

  const buildReference = (text: string) => {
    const matches = Array.from(text.matchAll(REFERENCE_PATTERN));

    if (matches.length === 0) {
      return text;
    }

    const parts: (string | JSX.Element)[] = [];
    let lastIndex = 0;

    for (const match of matches) {
      const matchIndex = match.index ?? 0;

      // Add text before the match
      if (matchIndex > lastIndex) {
        parts.push(text.slice(lastIndex, matchIndex));
      }

      const partyId = match[1];
      const indices = parseIndices(match[2]);

      // Create a citation pill for each index in the match
      for (const partyIndex of indices) {
        const displayNum = getDisplayNumber(partyId, partyIndex);
        const tooltip = getReferenceTooltip(partyId, partyIndex);

        if (displayNum > 0) {
          parts.push(
            <Tooltip key={`${partyId}-${partyIndex}-${matchIndex}`}>
              <TooltipTrigger>
                <span
                  className="mx-0.5 inline-flex cursor-pointer items-center justify-center rounded-full bg-zinc-300 px-2 py-0.5 text-xs transition-colors hover:bg-zinc-400 dark:bg-zinc-600 dark:hover:bg-zinc-500"
                  onClick={() => onReferenceClick(partyId, partyIndex)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      onReferenceClick(partyId, partyIndex);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  {displayNum}
                </span>
              </TooltipTrigger>
              {tooltip && (
                <TooltipContent className="max-w-96 text-ellipsis whitespace-nowrap">
                  {tooltip}
                </TooltipContent>
              )}
            </Tooltip>,
          );
        }
      }

      lastIndex = matchIndex + match[0].length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }

    return parts;
  };

  const processChildren = (children: React.ReactNode): React.ReactNode => {
    // Skip reference processing when no sources
    if (!hasSources) return children;

    if (typeof children === 'string') {
      const result = buildReference(children);
      return Array.isArray(result) ? <>{result}</> : result;
    }

    if (Array.isArray(children)) {
      return children.map((child, idx) => {
        if (typeof child === 'string') {
          const result = buildReference(child);
          return Array.isArray(result) ? (
            <span key={`text-${idx}-${child.slice(0, 10)}`}>{result}</span>
          ) : (
            result
          );
        }
        return child;
      });
    }

    return children;
  };

  const components: Partial<Components> = {
    p: ({ children, ...props }) => (
      <p className="mb-2 last:mb-0" {...props}>
        {processChildren(children)}
      </p>
    ),
    li: ({ children, ...props }) => (
      <li className="py-1" {...props}>
        {processChildren(children)}
      </li>
    ),
    em: ({ children, ...props }) => (
      <em {...props}>{processChildren(children)}</em>
    ),
    strong: ({ children, ...props }) => (
      <span className="font-semibold" {...props}>
        {processChildren(children)}
      </span>
    ),
    ol: ({ children, ...props }) => (
      <ol className="ml-4 list-outside list-decimal" {...props}>
        {children}
      </ol>
    ),
    ul: ({ children, ...props }) => (
      <ul className="ml-4 list-outside list-disc" {...props}>
        {children}
      </ul>
    ),
    a: ({ children, href, ...props }) => (
      <Link
        href={href || '#'}
        className="text-blue-500 hover:underline"
        target="_blank"
        rel="noreferrer"
        {...props}
      >
        {children}
      </Link>
    ),
    h1: ({ children, ...props }) => (
      <h1 className="mb-2 mt-4 text-lg font-semibold" {...props}>
        {children}
      </h1>
    ),
    h2: ({ children, ...props }) => (
      <h2 className="mb-2 mt-4 text-base font-semibold" {...props}>
        {children}
      </h2>
    ),
    h3: ({ children, ...props }) => (
      <h3 className="mb-2 mt-3 text-sm font-semibold" {...props}>
        {children}
      </h3>
    ),
    pre: ({ children, ...props }) => (
      <pre
        {...props}
        className="mt-2 w-full overflow-x-auto rounded-lg bg-zinc-100 p-3 text-sm dark:bg-zinc-800"
      >
        {children}
      </pre>
    ),
    code: ({ className, children, ...props }) => {
      const isCodeBlock = /language-(\w+)/.test(className || '');
      if (isCodeBlock) {
        return <code className={className}>{children}</code>;
      }
      return (
        <code
          className="rounded-md bg-zinc-100 px-1 py-0.5 text-sm dark:bg-zinc-800"
          {...props}
        >
          {children}
        </code>
      );
    },
    blockquote: ({ children, ...props }) => (
      <blockquote
        className="border-l-4 border-muted-foreground/30 pl-4 italic text-muted-foreground"
        {...props}
      >
        {children}
      </blockquote>
    ),
  };

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}

export const AgentMarkdown = memo(
  AgentChatMarkdownComponent,
  (prevProps, nextProps) =>
    prevProps.content === nextProps.content &&
    prevProps.sources === nextProps.sources,
);

export default AgentMarkdown;
