'use client';

import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { SliderWithLabels } from '@/modules/exploration-study/components/shared/slider-with-labels';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import type {
  AgeRange,
  DemographicsData,
  Education,
  Gender,
} from '@/modules/exploration-study/types';
import { useState } from 'react';

export interface DemographicsFormProps {
  onSubmit: (data: DemographicsData) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

const AGE_RANGE_OPTIONS: { value: AgeRange; label: string }[] = [
  { value: '18-24', label: '18-24 Jahre' },
  { value: '25-34', label: '25-34 Jahre' },
  { value: '35-44', label: '35-44 Jahre' },
  { value: '45-54', label: '45-54 Jahre' },
  { value: '55-64', label: '55-64 Jahre' },
  { value: '65+', label: '65 Jahre oder älter' },
];

const GENDER_OPTIONS: { value: Gender; label: string }[] = [
  { value: 'male', label: 'Männlich' },
  { value: 'female', label: 'Weiblich' },
  { value: 'diverse', label: 'Divers' },
  { value: 'prefer_not_to_say', label: 'Keine Angabe' },
];

const EDUCATION_OPTIONS: { value: Education; label: string }[] = [
  { value: 'no_degree', label: 'Kein Schulabschluss' },
  { value: 'hauptschule', label: 'Hauptschulabschluss' },
  { value: 'realschule', label: 'Realschulabschluss / Mittlere Reife' },
  { value: 'abitur', label: 'Abitur / Fachabitur' },
  { value: 'bachelor', label: 'Bachelor' },
  { value: 'master', label: 'Master / Diplom / Magister' },
  { value: 'doctorate', label: 'Promotion' },
  { value: 'other', label: 'Sonstiges' },
];

export function DemographicsForm({
  onSubmit,
  isSubmitting = false,
  className,
}: DemographicsFormProps) {
  const [ageRange, setAgeRange] = useState<AgeRange | ''>('');
  const [gender, setGender] = useState<Gender | ''>('');
  const [education, setEducation] = useState<Education | ''>('');
  const [politicalInterest, setPoliticalInterest] = useState(4);

  const isValid = ageRange !== '' && gender !== '' && education !== '';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isValid) {
      await onSubmit({
        ageRange: ageRange as AgeRange,
        gender: gender as Gender,
        education: education as Education,
        politicalInterest,
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Demografische Angaben</h1>
        <p className="text-sm text-muted-foreground">
          Bitte beantworte die folgenden Fragen zu deiner Person.
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="age-range">Altersgruppe</Label>
          <Select
            value={ageRange}
            onValueChange={(value) => setAgeRange(value as AgeRange)}
          >
            <SelectTrigger id="age-range">
              <SelectValue placeholder="Bitte auswählen" />
            </SelectTrigger>
            <SelectContent>
              {AGE_RANGE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="gender">Geschlecht</Label>
          <Select
            value={gender}
            onValueChange={(value) => setGender(value as Gender)}
          >
            <SelectTrigger id="gender">
              <SelectValue placeholder="Bitte auswählen" />
            </SelectTrigger>
            <SelectContent>
              {GENDER_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="education">Höchster Bildungsabschluss</Label>
          <Select
            value={education}
            onValueChange={(value) => setEducation(value as Education)}
          >
            <SelectTrigger id="education">
              <SelectValue placeholder="Bitte auswählen" />
            </SelectTrigger>
            <SelectContent>
              {EDUCATION_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <SliderWithLabels
          id="political-interest"
          label="Wie stark interessierst du dich für Politik?"
          value={politicalInterest}
          onChange={setPoliticalInterest}
          min={1}
          max={7}
          lowAnchor="Gar nicht"
          highAnchor="Sehr stark"
        />
      </div>

      <SubmitButton isSubmitting={isSubmitting} disabled={!isValid} />
    </form>
  );
}
