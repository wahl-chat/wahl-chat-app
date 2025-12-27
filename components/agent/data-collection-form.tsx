'use client';

import { useState } from 'react';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { User, MapPin, Home, Briefcase } from 'lucide-react';

const BUNDESLAENDER = [
  'Baden-Württemberg',
  'Bayern',
  'Berlin',
  'Brandenburg',
  'Bremen',
  'Hamburg',
  'Hessen',
  'Mecklenburg-Vorpommern',
  'Niedersachsen',
  'Nordrhein-Westfalen',
  'Rheinland-Pfalz',
  'Saarland',
  'Sachsen',
  'Sachsen-Anhalt',
  'Schleswig-Holstein',
  'Thüringen',
];

const LIVING_SITUATIONS = [
  { value: 'alone', label: 'Alleine' },
  { value: 'partner', label: 'Mit Partner/Partnerin' },
  { value: 'shared', label: 'Wohngemeinschaft' },
  { value: 'family', label: 'Mit Familie' },
];

const OCCUPATIONS = [
  { value: 'student_school', label: 'Schüler/Schülerin' },
  { value: 'student_uni', label: 'Ausbildung/Studium' },
  { value: 'employed', label: 'Angestelltenverhältnis' },
  { value: 'self_employed', label: 'Selbstständig' },
  { value: 'retired', label: 'In Rente' },
];

export default function DataCollectionForm() {
  const setUserData = useAgentStore((state) => state.setUserData);

  const [age, setAge] = useState<string>('');
  const [region, setRegion] = useState<string>('');
  const [livingSituation, setLivingSituation] = useState<string>('');
  const [occupation, setOccupation] = useState<string>('');

  const isValid =
    age &&
    Number.parseInt(age) >= 18 &&
    Number.parseInt(age) <= 120 &&
    region &&
    livingSituation &&
    occupation;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;

    setUserData({
      age: Number.parseInt(age),
      region,
      livingSituation,
      occupation,
    });
  };

  return (
    <div className="flex flex-col items-center p-4 py-8">
      <div className="w-full max-w-lg">
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">Datenerhebung</CardTitle>
            <CardDescription>
              Bitte geben Sie die folgenden Informationen ein, damit wir das
              Gespräch personalisieren können.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Age */}
              <div className="space-y-2">
                <Label
                  htmlFor="age"
                  className="flex items-center gap-2 text-sm font-medium"
                >
                  <User className="size-4 text-muted-foreground" />
                  Alter
                </Label>
                <Input
                  id="age"
                  type="number"
                  min={18}
                  max={120}
                  placeholder="Ihr Alter"
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  className="h-11"
                />
                {age && Number.parseInt(age) < 18 && (
                  <p className="text-sm text-destructive">
                    Sie müssen mindestens 18 Jahre alt sein, um teilzunehmen.
                  </p>
                )}
                {age && Number.parseInt(age) > 120 && (
                  <p className="text-sm text-destructive">
                    Bitte geben Sie ein gültiges Alter ein.
                  </p>
                )}
              </div>

              {/* Region */}
              <div className="space-y-2">
                <Label
                  htmlFor="region"
                  className="flex items-center gap-2 text-sm font-medium"
                >
                  <MapPin className="size-4 text-muted-foreground" />
                  Region
                </Label>
                <Select value={region} onValueChange={setRegion}>
                  <SelectTrigger id="region" className="h-11">
                    <SelectValue placeholder="Wählen Sie Ihre Region" />
                  </SelectTrigger>
                  <SelectContent>
                    {BUNDESLAENDER.map((land) => (
                      <SelectItem key={land} value={land}>
                        {land}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Living Situation */}
              <div className="space-y-2">
                <Label
                  htmlFor="living"
                  className="flex items-center gap-2 text-sm font-medium"
                >
                  <Home className="size-4 text-muted-foreground" />
                  Wohnsituation
                </Label>
                <Select
                  value={livingSituation}
                  onValueChange={setLivingSituation}
                >
                  <SelectTrigger id="living" className="h-11">
                    <SelectValue placeholder="Wählen Sie Ihre Wohnsituation" />
                  </SelectTrigger>
                  <SelectContent>
                    {LIVING_SITUATIONS.map((situation) => (
                      <SelectItem key={situation.value} value={situation.label}>
                        {situation.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Occupation */}
              <div className="space-y-2">
                <Label
                  htmlFor="occupation"
                  className="flex items-center gap-2 text-sm font-medium"
                >
                  <Briefcase className="size-4 text-muted-foreground" />
                  Beruf
                </Label>
                <Select value={occupation} onValueChange={setOccupation}>
                  <SelectTrigger id="occupation" className="h-11">
                    <SelectValue placeholder="Wählen Sie Ihren Beruf" />
                  </SelectTrigger>
                  <SelectContent>
                    {OCCUPATIONS.map((occ) => (
                      <SelectItem key={occ.value} value={occ.label}>
                        {occ.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Submit Button */}
              <Button
                type="submit"
                disabled={!isValid}
                className="h-11 w-full"
                size="lg"
              >
                Weiter
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

