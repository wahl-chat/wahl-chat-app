'use client';

import { Compass } from 'lucide-react';

interface ExplorationEmptyViewProps {
  onSuggestionClick: (suggestion: string) => void;
}

const SUGGESTIONS = [
  'Wie stehen die Parteien zur Mietpreisbremse?',
  'Was planen die Parteien für die Rente?',
  'Welche Klimaziele verfolgen die Parteien?',
  'Wie wollen die Parteien die Wirtschaft fördern?',
];

export function ExplorationEmptyView({
  onSuggestionClick,
}: ExplorationEmptyViewProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center p-4">
      <div className="max-w-md space-y-4 text-center">
        <div className="mx-auto flex size-20 items-center justify-center rounded-full bg-muted py-10">
          <Compass className="size-10 text-muted-foreground" />
        </div>
        <h1 className="text-xl font-semibold">Erkunde die Parteiprogramme</h1>
        <p className="text-sm text-muted-foreground">
          Stelle eine Frage zu einem politischen Thema und erkunde die
          Positionen der Parteien.
        </p>
        <div className="flex flex-wrap justify-center gap-2 pt-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => onSuggestionClick(s)}
              className="rounded-full border border-input px-3 py-2 text-xs text-muted-foreground hover:bg-muted"
              type="button"
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
