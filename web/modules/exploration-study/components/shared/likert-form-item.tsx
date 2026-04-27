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
  /** DOM id base; the heading gets `${id}-label`. */
  id: string;
  /** The question / item text rendered as the prominent heading. */
  label: string;
  leftAnchor: string;
  rightAnchor: string;
  min?: number;
  max?: number;
}

/**
 * Shared question card used by all Likert-scale questionnaires. Renders a
 * `FormItemCard` with a prominent heading and a numeric rating scale with
 * anchors below, wired into a react-hook-form `FormField`.
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
  const labelId = `${id}-label`;
  const optionCount = max - min + 1;

  return (
    <FormField
      control={control}
      name={name}
      render={({ field, fieldState }) => {
        const answered = field.value !== null && field.value !== undefined;
        const value = (field.value as number | null | undefined) ?? null;
        return (
          <FormItemCard answered={answered}>
            <FormItem className="space-y-4">
              <p
                id={labelId}
                className="pr-8 text-sm font-bold leading-snug text-foreground"
              >
                {label}
              </p>
              <FormControl>
                <RatingScale
                  id={id}
                  size={optionCount > 7 ? 'sm' : 'md'}
                  min={min}
                  max={max}
                  value={value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  lowAnchor={leftAnchor}
                  highAnchor={rightAnchor}
                  labelledById={labelId}
                  invalid={!!fieldState.error}
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
