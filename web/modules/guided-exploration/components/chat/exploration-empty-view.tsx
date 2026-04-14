'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import {
  Banknote,
  Briefcase,
  Compass,
  GraduationCap,
  Home,
  Leaf,
  type LucideIcon,
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
   * All default topic buttons become disabled with a tooltip explaining
   * that only the assigned topic has content in study mode.
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
            <Compass className="size-7 text-primary" />
          </div>
          <h1 className="text-xl font-semibold">Erkunde die Parteiprogramme</h1>
          <p className="text-sm text-muted-foreground">
            {isStudy
              ? 'In der Studie ist nur das dir zugewiesene Thema verfügbar. Wähle es aus oder stelle eine eigene Frage dazu.'
              : 'Wähle ein Thema oder stelle eine eigene Frage. Du kannst dann auswählen, welche Aspekte du genauer vergleichen möchtest.'}
          </p>
        </div>

        <TooltipProvider delayDuration={200}>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {studyTopic && (
              <button
                key={`study-${studyTopic.label}`}
                onClick={() => onSuggestionClick(studyTopic.label)}
                className="col-span-2 flex h-24 flex-col items-center justify-center gap-2 rounded-lg border-2 border-primary bg-primary/5 p-4 transition-colors hover:bg-primary/10 sm:col-span-3"
                type="button"
              >
                {(() => {
                  const Icon = studyTopic.icon ?? Scale;
                  return <Icon className="size-5 text-primary" />;
                })()}
                <span className="text-sm font-medium text-primary">
                  {studyTopic.label}
                </span>
              </button>
            )}
            {TOPICS.map((topic) => {
              const button = (
                <button
                  onClick={
                    isStudy ? undefined : () => onSuggestionClick(topic.label)
                  }
                  disabled={isStudy}
                  className={cn(
                    'flex h-24 w-full flex-col items-center justify-center gap-2 rounded-lg border border-input p-4 transition-colors',
                    isStudy
                      ? 'cursor-not-allowed opacity-50'
                      : 'hover:bg-muted',
                  )}
                  type="button"
                >
                  <topic.icon className="size-5 text-muted-foreground" />
                  <span className="text-sm font-medium">{topic.label}</span>
                </button>
              );

              if (!isStudy) {
                return <div key={topic.label}>{button}</div>;
              }

              return (
                <Tooltip key={topic.label}>
                  <TooltipTrigger asChild>
                    {/* Wrapper span so tooltip works on disabled button */}
                    <span className="block w-full">{button}</span>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs text-xs">
                    Im Studien-Modus nicht verfügbar – zu diesem Thema liegen
                    keine Informationen vor.
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        </TooltipProvider>
      </div>
    </div>
  );
}
