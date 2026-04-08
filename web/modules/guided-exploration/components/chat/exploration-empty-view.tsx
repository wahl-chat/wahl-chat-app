'use client';

import {
  Banknote,
  Briefcase,
  Compass,
  GraduationCap,
  Home,
  Leaf,
  ShieldCheck,
} from 'lucide-react';

interface ExplorationEmptyViewProps {
  onSuggestionClick: (suggestion: string) => void;
}

const TOPICS = [
  { label: 'Mieten & Wohnen', icon: Home },
  { label: 'Rente & Altersvorsorge', icon: Banknote },
  { label: 'Klima & Energie', icon: Leaf },
  { label: 'Migration & Sicherheit', icon: ShieldCheck },
  { label: 'Wirtschaft & Arbeit', icon: Briefcase },
  { label: 'Bildung & Forschung', icon: GraduationCap },
];

export function ExplorationEmptyView({
  onSuggestionClick,
}: ExplorationEmptyViewProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center p-4">
      <div className="max-w-lg space-y-6 text-center">
        <div className="space-y-2">
          <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-primary/10">
            <Compass className="size-7 text-primary" />
          </div>
          <h1 className="text-xl font-semibold">Erkunde die Parteiprogramme</h1>
          <p className="text-sm text-muted-foreground">
            Wähle ein Thema oder stelle eine eigene Frage. Du kannst dann
            auswählen, welche Aspekte du genauer vergleichen möchtest.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {TOPICS.map((topic) => (
            <button
              key={topic.label}
              onClick={() => onSuggestionClick(topic.label)}
              className="flex flex-col items-center gap-2 rounded-lg border border-input p-4 transition-colors hover:bg-muted"
              type="button"
            >
              <topic.icon className="size-5 text-muted-foreground" />
              <span className="text-sm font-medium">{topic.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
