'use client';

import { Markdown } from '@/components/markdown';
import { useMediaViewer } from '@/components/providers/media-viewer-provider';
import type { Source } from '@/lib/stores/chat-store.types';
import { getSourceMediaLinks } from '@/lib/utils';

type Props = {
  message: {
    content?: string;
    sources?: Source[];
  };
};

function ChatMarkdown({ message }: Props) {
  const mediaViewer = useMediaViewer();

  const onReferenceClick = (number: number) => {
    if (!message.sources) {
      return;
    }

    if (number < 0 || number >= message.sources.length) {
      return;
    }

    const source = message.sources[number];
    if (!source) {
      return;
    }
    // Open in the in-page media viewer (video/PDF), same as the "Quellen" list;
    // falls back to a new tab only when no provider is mounted.
    if (mediaViewer) {
      mediaViewer.openSource(source);
    } else if (source.url) {
      window.open(source.url, '_blank');
    }
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

  // Same helper the click handler uses, so the pill never disagrees with a click.
  const getReferenceIsVideo = (number: number) => {
    const source = message.sources?.[number];
    if (!source) {
      return false;
    }
    return getSourceMediaLinks(source).some((link) => link.kind === 'video');
  };

  return (
    <Markdown
      onReferenceClick={onReferenceClick}
      getReferenceTooltip={getReferenceTooltip}
      getReferenceName={getReferenceName}
      getReferenceIsVideo={getReferenceIsVideo}
    >
      {message.content ?? ''}
    </Markdown>
  );
}

export default ChatMarkdown;
