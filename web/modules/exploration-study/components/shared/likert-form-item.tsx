'use client';

import {
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@/components/ui/form';
import { FormItemCard } from '@/modules/exploration-study/components/shared/form-item-card';
import { RatingScale } from '@/modules/exploration-study/components/shared/rating-scale';
import type { Control, FieldPath, FieldValues } from 'react-hook-form';

export interface LikertFormItemProps<T extends FieldValues> {
  control: Control<T>;
  name: FieldPath<T>;
  /** DOM id base — shared `name` for the radio group. */
  id: string;
  /** The question / item text rendered inside the fieldset's <legend>. */
  label: string;
  leftAnchor: string;
  rightAnchor: string;
  min?: number;
  max?: number;
}

/**
 * Shared question card used by all Likert-scale questionnaires. The
 * `RatingScale` is a real `<fieldset>` + `<legend>` so the question becomes
 * the group's accessible name natively — no separate `<p>` + aria plumbing.
 */
export function LikertFormItem<T extends FieldValues>({
  control,
  name,
  id,
  label,
  leftAnchor,
  rightAnchor,
  min = 1,
  max = 7,
}: LikertFormItemProps<T>) {
  const optionCount = max - min + 1;

  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => {
        const answered = field.value !== null && field.value !== undefined;
        const value = (field.value as number | null | undefined) ?? null;
        return (
          <FormItemCard answered={answered}>
            <FormItem className="space-y-4">
              <FormControl>
                <RatingScale
                  id={id}
                  legend={label}
                  size={optionCount > 7 ? 'sm' : 'md'}
                  min={min}
                  max={max}
                  value={value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  lowAnchor={leftAnchor}
                  highAnchor={rightAnchor}
                  required
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          </FormItemCard>
        );
      }}
    />
  );
}
