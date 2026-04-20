'use client';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import { Check, Compass } from 'lucide-react';
import { useState } from 'react';

import type { TopicDirectionsEvent } from '@/modules/guided-exploration/types';

interface TopicDirectionsCardProps {
  directions: TopicDirectionsEvent;
  onSelectDirections: (directions: Array<{ id: string; name: string }>) => void;
  isLoading?: boolean;
  /** Direction names the user already selected (persisted) */
  selectedDirections?: string[];
  /** Minimum number of directions the user must select before submitting */
  minSelections?: number;
}

export function TopicDirectionsCard({
  directions,
  onSelectDirections,
  isLoading = false,
  selectedDirections,
  minSelections = 1,
}: TopicDirectionsCardProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const isCompleted = selectedDirections && selectedDirections.length > 0;

  const allIds = directions.directions.map((d) => d.id);
  const allSelected =
    allIds.length > 0 && allIds.every((id) => selected.has(id));

  const toggleDirection = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(allIds));
    }
  };

  const handleSubmit = () => {
    const dirs = directions.directions
      .filter((d) => selected.has(d.id))
      .map((d) => ({ id: d.id, name: d.name }));
    onSelectDirections(dirs);
  };

  // Completed state: show which directions were selected
  if (isCompleted) {
    const selectedSet = new Set(selectedDirections);

    return (
      <section
        aria-label="Ausgewählte Erkundungsrichtungen"
        className="space-y-2"
      >
        {directions.directions.map((direction) => {
          const wasSelected = selectedSet.has(direction.name);

          return (
            <div
              key={direction.id}
              aria-label={`${direction.name}: ${wasSelected ? 'ausgewählt' : 'nicht ausgewählt'}`}
              className={cn(
                'flex items-start gap-3 rounded-lg border p-3',
                wasSelected
                  ? 'border-primary/20 bg-primary/5'
                  : 'border-transparent opacity-40',
              )}
            >
              <div
                aria-hidden="true"
                className={cn(
                  'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded',
                  wasSelected
                    ? 'bg-primary text-primary-foreground'
                    : 'border border-muted-foreground/30',
                )}
              >
                {wasSelected && <Check className="size-3" />}
              </div>
              <div className="space-y-1">
                <p
                  className={cn(
                    'text-base font-bold text-foreground',
                    !wasSelected && 'opacity-60',
                  )}
                >
                  {direction.name}
                </p>
                {wasSelected && (
                  <p className="text-sm font-normal text-foreground">
                    {direction.hook}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </section>
    );
  }

  // Interactive state: checkboxes with submit
  const headingId = 'topic-directions-heading';
  return (
    <section aria-labelledby={headingId} role="group" className="space-y-3">
      <h2 id={headingId} className="text-base font-bold text-foreground">
        Ich habe mehrere Aspekte zu diesem Thema gefunden. Wähle aus, was dich
        interessiert — du kannst auch mehrere Aspekte auswählen.
      </h2>

      <div className="space-y-2">
        {directions.directions.map((direction) => {
          const isChecked = selected.has(direction.id);
          const inputId = `direction-${direction.id}`;
          const labelTextId = `${inputId}-label`;
          const hookId = `${inputId}-hook`;
          return (
            <label
              key={direction.id}
              htmlFor={inputId}
              className={cn(
                'flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-muted has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
                isChecked ? 'border-primary/30 bg-primary/5' : 'border-input',
                isLoading && 'pointer-events-none opacity-60',
              )}
            >
              <Checkbox
                id={inputId}
                checked={isChecked}
                onCheckedChange={() => toggleDirection(direction.id)}
                disabled={isLoading}
                aria-labelledby={labelTextId}
                aria-describedby={hookId}
                className="mt-1"
              />
              <div className="space-y-1">
                <p
                  id={labelTextId}
                  className="text-base font-bold text-foreground"
                >
                  {direction.name}
                </p>
                <p id={hookId} className="text-sm font-normal text-foreground">
                  {direction.hook}
                </p>
              </div>
            </label>
          );
        })}

        {/* Select all option */}
        <label
          htmlFor="direction-select-all"
          className={cn(
            'flex cursor-pointer items-center gap-3 rounded-lg border border-dashed p-4 transition-colors hover:bg-muted has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
            allSelected ? 'border-primary/30 bg-primary/5' : 'border-input',
            isLoading && 'pointer-events-none opacity-60',
          )}
        >
          <Checkbox
            id="direction-select-all"
            checked={allSelected}
            onCheckedChange={toggleAll}
            disabled={isLoading}
            aria-label="Alle Aspekte erkunden"
          />
          <div className="flex items-center gap-2">
            <Compass className="size-4 text-foreground" aria-hidden="true" />
            <span
              className="text-base font-bold text-foreground"
              aria-hidden="true"
            >
              Alle Aspekte erkunden
            </span>
          </div>
        </label>
      </div>

      <Button
        onClick={handleSubmit}
        disabled={isLoading || selected.size < minSelections}
        className="w-full text-base font-bold"
      >
        Erkundung starten
        {selected.size > 0 && (
          <span className="ml-1 text-sm font-normal opacity-80">
            ({selected.size} ausgewählt)
          </span>
        )}
      </Button>
      {minSelections > 1 && selected.size < minSelections && (
        <p className="text-center text-sm font-normal text-foreground">
          Bitte wähle mindestens {minSelections} Aspekte aus.
        </p>
      )}
    </section>
  );
}
