'use client';

import { Markdown } from '@/components/markdown';
import type { Source } from '@/lib/stores/chat-store.types';
import { buildPdfUrl } from '@/lib/utils';

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

  return (
    <Markdown
      onReferenceClick={onReferenceClick}
      getReferenceTooltip={getReferenceTooltip}
      getReferenceName={getReferenceName}
    >
      {message.content ?? ''}
    </Markdown>
  );
}

export default ChatMarkdown;
