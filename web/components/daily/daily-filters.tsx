'use client';

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { DAILY_STATES, type StateSelection } from '@/lib/daily/region';
import { DAILY_TOPIC_KEYS } from '@/lib/daily/topics';
import { cn } from '@/lib/utils';
import { MapPinIcon } from 'lucide-react';
import TopicChip from './topic-chip';

type Props = {
  state: StateSelection;
  onStateChange: (state: StateSelection) => void;
  topics: string[];
  onTopicsChange: (topics: string[]) => void;
};

const STATE_OPTIONS: { value: StateSelection; label: string }[] = [
  ...Object.entries(DAILY_STATES).map(([value, { name }]) => ({
    value: value as StateSelection,
    label: name,
  })),
  { value: 'none', label: 'Anderes Bundesland (nur Bundestag)' },
];

function DailyFilters({ state, onStateChange, topics, onTopicsChange }: Props) {
  const toggle = (topic: string) =>
    onTopicsChange(
      topics.includes(topic)
        ? topics.filter((t) => t !== topic)
        : [...topics, topic],
    );

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-muted-foreground">
          Dein Bundesland
        </span>
        <Select
          value={state}
          onValueChange={(value) => onStateChange(value as StateSelection)}
        >
          <SelectTrigger
            className="w-full bg-muted/50 md:w-80"
            aria-label="Bundesland auswählen"
          >
            <span className="flex items-center gap-2">
              <MapPinIcon className="size-4 text-muted-foreground" />
              <SelectValue />
            </span>
          </SelectTrigger>
          <SelectContent>
            {STATE_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-medium text-muted-foreground">
          Deine Themen
        </span>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            aria-pressed={topics.length === 0}
            onClick={() => onTopicsChange([])}
            className={cn(
              'h-7 rounded-md border border-border px-2 text-xs font-medium',
              topics.length === 0
                ? 'bg-foreground text-background'
                : 'bg-transparent hover:bg-muted',
            )}
          >
            Alle Themen
          </button>
          {DAILY_TOPIC_KEYS.map((topic) => (
            <TopicChip
              key={topic}
              topic={topic}
              active={topics.includes(topic)}
              onClick={() => toggle(topic)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default DailyFilters;
