'use client';

import { Markdown } from '@/components/markdown';
import VisuallyHidden from '@/components/visually-hidden';
import type { Source } from '@/lib/stores/chat-store.types';
import { buildPdfUrl } from '@/lib/utils';
import { useMemo } from 'react';

type Props = {
  message: {
    content?: string;
    sources?: Source[];
  };
};

function ChatMarkdown({ message }: Props) {
  const onReferenceClick = (number: number) => {
    if (!message.sources) {
      return;
    }

    if (number < 0 || number >= message.sources.length) {
      return;
    }

    const source = message.sources[number];
    const isPdfLink = source?.url.includes('.pdf');

    if (source && isPdfLink && window) {
      const url = buildPdfUrl(source);
      return window.open(url.toString(), '_blank');
    }

    window.open(source.url, '_blank');
  };

  const getReferenceTooltip = (number: number) => {
    if (!message.sources) {
      return null;
    }

    if (number < 0 || number >= message.sources.length) {
      return null;
    }

    const source = message.sources[number];
    if (!source) {
      return null;
    }

    return `${source.source} - Seite: ${source.page}`;
  };

  const getReferenceName = (number: number) => {
    if (!message.sources) {
      return null;
    }

    if (number < 0 || number >= message.sources.length) {
      return null;
    }

    const source = message.sources[number];
    if (!source) {
      return null;
    }

    return `${number + 1}`;
  };

  const referencedSources = useMemo(() => {
    if (!message.sources || message.sources.length === 0) return [];

    const regex = /\[(\d+(?:\s*,\s*\d+)*)\]/g;
    const matches = message.content?.match(regex);
    if (!matches) return [];

    const numbers = matches.flatMap((match) => {
      const nums = match.match(/^\[(\d+(?:\s*,\s*\d+)*)\]$/);
      if (!nums) return [];
      return nums[1].split(',').map((n) => Number.parseInt(n.trim()));
    });

    const uniqueNumbers = [...new Set(numbers)].sort((a, b) => a - b);

    return uniqueNumbers
      .filter((n) => n >= 0 && n < (message.sources?.length ?? 0))
      .map((n) => ({ number: n + 1, source: message.sources?.[n] }));
  }, [message.content, message.sources]);

  return (
    <>
      <Markdown
        onReferenceClick={onReferenceClick}
        getReferenceTooltip={getReferenceTooltip}
        getReferenceName={getReferenceName}
      >
        {message.content ?? ''}
      </Markdown>
      {referencedSources.length > 0 && (
        <VisuallyHidden>
          <h3>Quellen</h3>
          <ul>
            {referencedSources.map(({ number, source }) => (
              <li key={number}>
                Quelle {number}: {source?.source}, Seite {source?.page}
              </li>
            ))}
          </ul>
        </VisuallyHidden>
      )}
    </>
  );
}

export default ChatMarkdown;
