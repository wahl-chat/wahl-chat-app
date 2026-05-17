'use client';

import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { LikertFormItem } from '@/modules/exploration-study/components/shared/likert-form-item';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import {
  type CognitiveLoadFormValues,
  cognitiveLoadSchema,
} from '@/modules/exploration-study/schemas/forms';
import {
  COGNITIVE_LOAD_ANCHORS,
  COGNITIVE_LOAD_ITEMS,
  type CognitiveLoadResponse,
} from '@/modules/exploration-study/types';
import { zodResolver } from '@hookform/resolvers/zod';
import type { FieldPath } from 'react-hook-form';
import { useForm } from 'react-hook-form';

export interface CognitiveLoadFormSubmitData {
  cognitiveLoad: CognitiveLoadResponse;
  attentionCheck: number;
}

export interface CognitiveLoadFormProps {
  onSubmit: (data: CognitiveLoadFormSubmitData) => void;
  // When true, renders an optional free-text field for qualitative studies.
  showQualitativeFeedback?: boolean;
  className?: string;
}

const QUALITATIVE_FEEDBACK_LABEL =
  'Möchtest du noch etwas zu deiner Wahrnehmung der Aufgabenbelastung ergänzen? (optional)';

// Position 4 of 8 — surrounded on both sides by real CL items so the check
// blends into the block visually and answer-format-wise.
const ATTENTION_CHECK_INSERT_INDEX = 3;

const ATTENTION_CHECK_LABEL =
  'Dies ist eine Aufmerksamkeitsfrage. Bitte wähle für diese Aussage den Wert 2.';

export function CognitiveLoadForm({
  onSubmit,
  showQualitativeFeedback = false,
  className,
}: CognitiveLoadFormProps) {
  const form = useForm<CognitiveLoadFormValues>({
    resolver: zodResolver(cognitiveLoadSchema),
    defaultValues: {},
  });

  const handleSubmit = form.handleSubmit((values) => {
    const { attentionCheck, qualitativeFeedback, ...clItems } = values;
    const cognitiveLoad: CognitiveLoadResponse = {
      ...clItems,
      ...(qualitativeFeedback ? { qualitativeFeedback } : {}),
    };
    onSubmit({ cognitiveLoad, attentionCheck });
  });

  const itemsBefore = COGNITIVE_LOAD_ITEMS.slice(
    0,
    ATTENTION_CHECK_INSERT_INDEX,
  );
  const itemsAfter = COGNITIVE_LOAD_ITEMS.slice(ATTENTION_CHECK_INSERT_INDEX);

  return (
    <Form {...form}>
      <form
        onSubmit={handleSubmit}
        aria-labelledby="cognitive-load-heading"
        className={cn('space-y-6', className)}
      >
        <div className="space-y-2">
          <h2 id="cognitive-load-heading" className="text-xl font-semibold">
            Bewertung der Aufgabe
          </h2>
          <p className="text-sm text-foreground">
            Bitte gib für jede Aussage an, wie sehr sie auf die gerade
            bearbeitete Aufgabe zutrifft.
          </p>
        </div>

        <div className="space-y-3">
          {itemsBefore.map((item) => (
            <LikertFormItem
              key={item.id}
              control={form.control}
              name={item.id as FieldPath<CognitiveLoadFormValues>}
              id={`cognitive-load-${item.id}`}
              label={item.text}
              leftAnchor={COGNITIVE_LOAD_ANCHORS.low}
              rightAnchor={COGNITIVE_LOAD_ANCHORS.high}
              min={1}
              max={7}
            />
          ))}
          <LikertFormItem
            control={form.control}
            name="attentionCheck"
            id="cognitive-load-attention-check"
            label={ATTENTION_CHECK_LABEL}
            leftAnchor={COGNITIVE_LOAD_ANCHORS.low}
            rightAnchor={COGNITIVE_LOAD_ANCHORS.high}
            min={1}
            max={7}
          />
          {itemsAfter.map((item) => (
            <LikertFormItem
              key={item.id}
              control={form.control}
              name={item.id as FieldPath<CognitiveLoadFormValues>}
              id={`cognitive-load-${item.id}`}
              label={item.text}
              leftAnchor={COGNITIVE_LOAD_ANCHORS.low}
              rightAnchor={COGNITIVE_LOAD_ANCHORS.high}
              min={1}
              max={7}
            />
          ))}
        </div>

        {showQualitativeFeedback && (
          <FormField
            control={form.control}
            name="qualitativeFeedback"
            render={({ field }) => (
              <FormItem>
                <FormLabel htmlFor="cognitive-load-qualitative-feedback">
                  {QUALITATIVE_FEEDBACK_LABEL}
                </FormLabel>
                <FormControl>
                  <Textarea
                    {...field}
                    id="cognitive-load-qualitative-feedback"
                    value={field.value ?? ''}
                    rows={4}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        <SubmitButton />
      </form>
    </Form>
  );
}
