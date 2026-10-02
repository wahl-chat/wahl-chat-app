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
import Image from 'next/image';
import { CARD_SURFACE, INK_BORDER } from './card-styles';
import TopicChip from './topic-chip';

const FIELD_LABEL =
  'text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--daily-muted)]';

type Props = {
  state: StateSelection;
  onStateChange: (state: StateSelection) => void;
  topics: string[];
  onTopicsChange: (topics: string[]) => void;
};

// Coats of arms of the elections we cover; the federal eagle stands for the
// Bundestag-only default.
const STATE_OPTIONS: { value: StateSelection; label: string; sigil: string }[] =
  [
    {
      value: 'none',
      label: 'Standard: Bundestag',
      sigil: '/images/bundestagswahl-2025.webp',
    },
    {
      value: 'ST',
      label: DAILY_STATES.ST.name,
      sigil: '/images/landtagswahl-sachsen-anhalt-2026.webp',
    },
    {
      value: 'BW',
      label: DAILY_STATES.BW.name,
      sigil: '/images/landtagswahl-baden-wuerttemberg-2026.webp',
    },
  ];

function StateOption({ option }: { option: (typeof STATE_OPTIONS)[number] }) {
  return (
    <span className="flex items-center gap-2.5">
      <Image
        src={option.sigil}
        alt=""
        width={20}
        height={20}
        className="size-5 object-contain"
      />
      {option.label}
    </span>
  );
}

function DailyFilters({ state, onStateChange, topics, onTopicsChange }: Props) {
  const selectedOption = STATE_OPTIONS.find((o) => o.value === state);
  const toggle = (topic: string) =>
    onTopicsChange(
      topics.includes(topic)
        ? topics.filter((t) => t !== topic)
        : [...topics, topic],
    );

  return (
    <div className={cn(CARD_SURFACE, 'flex flex-col gap-5 p-5')}>
      <div className="flex flex-col gap-2">
        <span className={FIELD_LABEL}>Dein Bundesland</span>
        <Select
          value={state}
          onValueChange={(value) => onStateChange(value as StateSelection)}
        >
          <SelectTrigger
            className={cn(
              INK_BORDER,
              'h-11 w-full rounded-[4px] bg-[var(--daily-canvas)] font-medium shadow-[2px_2px_0_0_var(--daily-ink)] focus:ring-[var(--daily-ink)] md:w-80',
            )}
            aria-label="Bundesland auswählen"
          >
            <SelectValue>
              {selectedOption && <StateOption option={selectedOption} />}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {STATE_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                <StateOption option={option} />
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-2">
        <span className={FIELD_LABEL}>Deine Themen</span>
        {/* Mobile: three rows that scroll sideways; md+: one wrapping block.
            The padding keeps the chips' offset shadows inside the scroller. */}
        <div className="-mx-5 grid auto-cols-max grid-flow-col grid-rows-3 gap-2.5 overflow-x-auto px-5 pb-1.5 [scrollbar-width:none] md:mx-0 md:flex md:flex-wrap md:overflow-visible md:px-0 md:pb-0 [&::-webkit-scrollbar]:hidden">
          <button
            type="button"
            aria-pressed={topics.length === 0}
            onClick={() => onTopicsChange([])}
            className={cn(
              'h-8 rounded-[4px] border-2 border-[var(--daily-ink)] px-2.5 text-xs font-bold transition-[transform,box-shadow] duration-100 motion-reduce:transition-none',
              topics.length === 0
                ? 'translate-x-[2px] translate-y-[2px] bg-[var(--daily-ink)] text-[var(--daily-canvas)]'
                : 'bg-[var(--daily-surface)] shadow-[2px_2px_0_0_var(--daily-ink)] hover:-translate-x-px hover:-translate-y-px motion-reduce:transform-none',
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
