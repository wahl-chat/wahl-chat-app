'use client';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import { Compass } from 'lucide-react';
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

  // Completed state: collapse to a single inline summary line. tabIndex={-1} +
  // the data hook make it the focus target the chat view moves to on submit,
  // so the selection is read aloud instead of focus dropping to <body> when the
  // interactive submit button unmounts.
  if (isCompleted) {
    return (
      <p
        data-directions-summary
        tabIndex={-1}
        className="text-sm text-foreground outline-none"
      >
        <strong className="font-semibold">Erkundet wird:</strong>{' '}
        {selectedDirections.join(' · ')}
      </p>
    );
  }

  // Interactive state: checkboxes with submit. <fieldset>/<legend> is the
  // native semantic for a checkbox group with a question.
  return (
    <fieldset className="m-0 min-w-0 space-y-3 border-0 p-0">
      <legend className="text-sm text-foreground">
        Ich schaue für dich nach, was die Parteien zu diesem Thema sagen. Du
        kannst steuern, worauf ich den Fokus lege — wähle einen oder mehrere
        Aspekte aus.
      </legend>

      <div className="space-y-2">
        {directions.directions.map((direction) => {
          const isChecked = selected.has(direction.id);
          const inputId = `direction-${direction.id}`;
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
                className="mt-0.5"
              />
              <div className="space-y-0.5">
                <span className="block text-sm font-semibold text-foreground">
                  {direction.name}
                </span>
                <span
                  aria-hidden="true"
                  className="block text-sm font-normal text-foreground"
                >
                  {direction.hook}
                </span>
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
          />
          <span className="flex items-center gap-2">
            <Compass className="size-4 text-foreground" aria-hidden="true" />
            <span className="text-sm font-semibold text-foreground">
              Alle Aspekte erkunden
            </span>
          </span>
        </label>
      </div>

      <Button
        onClick={handleSubmit}
        disabled={isLoading || selected.size < minSelections}
        className="w-full"
      >
        Erkundung starten
        {selected.size > 0 && (
          <span className="ml-1 text-xs font-normal opacity-80">
            ({selected.size} ausgewählt)
          </span>
        )}
      </Button>
      {minSelections > 1 && selected.size < minSelections && (
        <p className="text-center text-sm text-foreground">
          Bitte wähle mindestens {minSelections} Aspekte aus.
        </p>
      )}
    </fieldset>
  );
}
