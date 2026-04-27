'use client';

import { cn } from '@/lib/utils';
import {
  Banknote,
  Briefcase,
  Compass,
  GraduationCap,
  Home,
  Leaf,
  type LucideIcon,
  MousePointerClick,
  Scale,
  ShieldCheck,
} from 'lucide-react';

interface StudyTopicRestriction {
  /** The label of the only allowed topic (e.g. "Klimaschutz"). */
  label: string;
  /** Optional icon override for the allowed topic. */
  icon?: LucideIcon;
}

interface ExplorationEmptyViewProps {
  onSuggestionClick: (suggestion: string) => void;
  /**
   * When set, restricts topic buttons to the single allowed study topic.
   * All default topics are rendered as non-interactive muted cards with an
   * explanatory caption — no disabled buttons, no tooltips on hidden focus.
   */
  studyTopic?: StudyTopicRestriction;
}

const TOPICS: { label: string; icon: LucideIcon }[] = [
  { label: 'Mieten & Wohnen', icon: Home },
  { label: 'Rente & Altersvorsorge', icon: Banknote },
  { label: 'Klima & Energie', icon: Leaf },
  { label: 'Migration & Sicherheit', icon: ShieldCheck },
  { label: 'Wirtschaft & Arbeit', icon: Briefcase },
  { label: 'Bildung & Forschung', icon: GraduationCap },
];

export function ExplorationEmptyView({
  onSuggestionClick,
  studyTopic,
}: ExplorationEmptyViewProps) {
  const isStudy = Boolean(studyTopic);

  return (
    <div className="flex flex-1 flex-col items-center justify-center p-4">
      <div className="max-w-lg space-y-6 text-center">
        <div className="space-y-2">
          <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-primary/10">
            <Compass className="size-7 text-primary" aria-hidden="true" />
          </div>
          <h1 className="text-xl font-semibold">Erkunde die Parteiprogramme</h1>
          <p className="text-sm text-foreground">
            {isStudy
              ? 'In der Studie ist nur das dir zugewiesene Thema verfügbar. Wähle es aus oder stelle eine eigene Frage dazu.'
              : 'Wähle ein Thema oder stelle eine eigene Frage. Du kannst dann auswählen, welche Aspekte du genauer vergleichen möchtest.'}
          </p>
        </div>

        <nav
          aria-label="Themen auswählen"
          className="grid grid-cols-2 gap-2 sm:grid-cols-3"
        >
          {studyTopic && (
            <button
              key={`study-${studyTopic.label}`}
              onClick={() => onSuggestionClick(studyTopic.label)}
              className="group col-span-2 flex h-28 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-primary bg-primary/5 p-4 transition-all hover:scale-[1.02] hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:col-span-3"
              type="button"
              aria-label={`${studyTopic.label} — klicken zum Starten`}
            >
              {(() => {
                const Icon = studyTopic.icon ?? Scale;
                return (
                  <Icon className="size-5 text-primary" aria-hidden="true" />
                );
              })()}
              <span className="text-sm font-medium text-primary">
                {studyTopic.label}
              </span>
              <span className="flex items-center gap-1 text-xs text-primary/80">
                <MousePointerClick
                  className="size-3.5 transition-transform group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
                Klicken zum Starten
              </span>
            </button>
          )}
          {TOPICS.map((topic) => {
            if (isStudy) {
              return (
                <div
                  key={topic.label}
                  aria-hidden="true"
                  className="flex h-24 flex-col items-center justify-center gap-2 rounded-lg border border-input p-4 opacity-40"
                >
                  <topic.icon className="size-5 text-foreground" />
                  <span className="text-sm font-medium text-foreground">
                    {topic.label}
                  </span>
                </div>
              );
            }
            return (
              <button
                key={topic.label}
                onClick={() => onSuggestionClick(topic.label)}
                className={cn(
                  'flex h-24 w-full flex-col items-center justify-center gap-2 rounded-lg border border-input p-4 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                )}
                type="button"
              >
                <topic.icon
                  className="size-5 text-foreground"
                  aria-hidden="true"
                />
                <span className="text-sm font-medium">{topic.label}</span>
              </button>
            );
          })}
        </nav>

        {isStudy && (
          <p className="text-xs text-foreground">
            Weitere Themen sind im Studien-Modus nicht verfügbar – zu diesen
            Themen liegen keine Informationen vor.
          </p>
        )}
      </div>
    </div>
  );
}
