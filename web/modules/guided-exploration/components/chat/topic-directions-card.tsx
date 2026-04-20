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
}

export function TopicDirectionsCard({
  directions,
  onSelectDirections,
  isLoading = false,
  selectedDirections,
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
              <div className="space-y-0.5">
                <p
                  className={cn(
                    'text-sm font-medium',
                    !wasSelected && 'text-muted-foreground',
                  )}
                >
                  {direction.name}
                </p>
                {wasSelected && (
                  <p className="text-xs text-muted-foreground">
                    {direction.description}
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
      <h2 id={headingId} className="text-sm font-medium">
        Ich habe mehrere Aspekte zu diesem Thema gefunden. Wähle aus, was dich
        interessiert — du kannst auch mehrere Aspekte auswählen.
      </h2>

      <div className="space-y-2">
        {directions.directions.map((direction) => {
          const isChecked = selected.has(direction.id);
          const inputId = `direction-${direction.id}`;
          const labelTextId = `${inputId}-label`;
          const descriptionIds = [`${inputId}-description`];
          if (direction.suggestedQuestion) {
            descriptionIds.push(`${inputId}-question`);
          }
          return (
            <label
              key={direction.id}
              htmlFor={inputId}
              className={cn(
                'flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
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
                aria-describedby={descriptionIds.join(' ')}
                className="mt-0.5"
              />
              <div className="space-y-1">
                <p id={labelTextId} className="text-sm font-medium">
                  {direction.name}
                </p>
                <p
                  id={`${inputId}-description`}
                  className="text-xs text-muted-foreground"
                >
                  {direction.description}
                </p>
                <p
                  className="text-xs italic text-muted-foreground/80"
                  aria-hidden="true"
                >
                  {direction.partyStancesPreview}
                </p>
                {direction.suggestedQuestion && (
                  <p
                    id={`${inputId}-question`}
                    className="mt-1 text-xs text-primary/70"
                  >
                    <span aria-hidden="true">&rarr; </span>
                    {direction.suggestedQuestion}
                  </p>
                )}
              </div>
            </label>
          );
        })}

        {/* Select all option */}
        <label
          htmlFor="direction-select-all"
          className={cn(
            'flex cursor-pointer items-center gap-3 rounded-lg border border-dashed p-3 transition-colors hover:bg-muted has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
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
          <div className="flex items-center gap-1.5">
            <Compass
              className="size-3.5 text-muted-foreground"
              aria-hidden="true"
            />
            <span className="text-sm font-medium" aria-hidden="true">
              Alle Aspekte erkunden
            </span>
          </div>
        </label>
      </div>

      <Button
        onClick={handleSubmit}
        disabled={isLoading || selected.size === 0}
        className="w-full"
      >
        Erkundung starten
        {selected.size > 0 && (
          <span className="ml-1 text-xs opacity-70">
            ({selected.size} ausgewählt)
          </span>
        )}
      </Button>
    </section>
  );
}
