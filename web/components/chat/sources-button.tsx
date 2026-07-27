import { Button } from '@/components/ui/button';
import type { Source } from '@/lib/stores/chat-store.types';
import { BookMarkedIcon } from 'lucide-react';
import { useMemo } from 'react';
import { type NumberedSource, SourcesDialog } from './sources-dialog';

type Props = {
  sources: Source[];
  messageContent: string;
};

function SourcesButton({ sources, messageContent }: Props) {
  const [sourcesReferenced, sourcesNotReferenced] = useMemo(() => {
    const regex = /\[(\d+(?:\s*,\s*\d+)*)\]/g;
    const matches = messageContent.match(regex);

    const numbers = matches?.flatMap((match) => {
      const numbers = match.match(/^\[(\d+(?:\s*,\s*\d+)*)\]$/);

      if (!numbers) return [];
      const numbersArray = numbers[1].split(',');
      return numbersArray.map((number) => Number.parseInt(number));
    });

    // Drop citation indices that point past the sources array — an over-citation
    // (`[5]` with 3 sources) would otherwise spread `undefined` into a ghost row.
    const uniqueNumbers = [...new Set(numbers)].filter(
      (number) => sources[number] != null,
    );

    const toNumbered = (index: number): NumberedSource => ({
      source: sources[index],
      // Badge is 1-based; the in-text citation uses the 0-based array index.
      displayNumber: index + 1,
    });

    const referenced = uniqueNumbers.map(toNumbered);

    const notReferenced = sources
      .map((_, index) => index)
      .filter((number) => !uniqueNumbers.includes(number))
      .map(toNumbered);

    return [
      referenced.sort((a, b) => a.displayNumber - b.displayNumber),
      notReferenced.sort((a, b) => a.displayNumber - b.displayNumber),
    ];
  }, [messageContent, sources]);

  if (sourcesReferenced.length === 0 && sourcesNotReferenced.length === 0) {
    return null;
  }

  return (
    <SourcesDialog
      referenced={sourcesReferenced}
      notReferenced={sourcesNotReferenced}
      trigger={
        <Button
          variant="outline"
          className="h-8 px-2 text-xs group-data-[has-message-background]:bg-zinc-100 group-data-[has-message-background]:hover:bg-zinc-200 group-data-[has-message-background]:dark:bg-zinc-900 group-data-[has-message-background]:dark:hover:bg-zinc-800"
        >
          <BookMarkedIcon />
          Quellen
        </Button>
      }
    />
  );
}

export default SourcesButton;
