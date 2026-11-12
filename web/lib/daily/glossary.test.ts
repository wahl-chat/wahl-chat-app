import { describe, expect, it } from 'bun:test';
import type { GlossaryEntry } from '@/lib/firebase/firebase.types';
import { splitByRefs, splitLabel } from './glossary';

const entry = (
  term_id: string,
  term: string,
  forms: string[],
): GlossaryEntry => ({
  term_id,
  term,
  definition: `${term} erklärt.`,
  forms,
});

const glossary = {
  'aktuelle-stunde': entry('aktuelle-stunde', 'Aktuelle Stunde', [
    'Aktuelle Stunde',
    'Aktuellen Stunde',
  ]),
  'parlamentarischer-staatssekretaer': entry(
    'parlamentarischer-staatssekretaer',
    'Parlamentarischer Staatssekretär',
    ['Parlamentarischer Staatssekretär', 'Parlamentarische Staatssekretärin'],
  ),
  staatssekretaer: entry('staatssekretaer', 'Staatssekretär', [
    'Staatssekretärin',
  ]),
  obmann: entry('obmann', 'Obmann', ['Obmann', 'Obfrau']),
};

describe('splitByRefs', () => {
  it('marks the first occurrence of each referenced term', () => {
    const parts = splitByRefs(
      'In der Aktuellen Stunde, einer Aktuellen Stunde zur Bahn.',
      [{ term_id: 'aktuelle-stunde', surface: 'Aktuellen Stunde' }],
      glossary,
    );
    expect(parts.map((p) => [p.text, p.entry?.term_id ?? null])).toEqual([
      ['In der ', null],
      ['Aktuellen Stunde', 'aktuelle-stunde'],
      [', einer Aktuellen Stunde zur Bahn.', null],
    ]);
  });

  it('leaves the text plain when the entry is not verified (absent)', () => {
    expect(
      splitByRefs(
        'Die Beschlussempfehlung.',
        [{ term_id: 'beschlussempfehlung', surface: 'Beschlussempfehlung' }],
        glossary,
      ),
    ).toEqual([{ text: 'Die Beschlussempfehlung.' }]);
  });

  it('matches whole words only', () => {
    const parts = splitByRefs(
      'Kein Aktuelle Stundenlohn.',
      [{ term_id: 'aktuelle-stunde', surface: 'Aktuelle Stunde' }],
      glossary,
    );
    expect(parts).toEqual([{ text: 'Kein Aktuelle Stundenlohn.' }]);
  });
});

describe('splitLabel', () => {
  it('prefers the longest form', () => {
    const parts = splitLabel(
      'Parlamentarische Staatssekretärin beim Bundesminister der Finanzen',
      glossary,
    );
    expect(parts[0]).toEqual({
      text: 'Parlamentarische Staatssekretärin',
      entry: glossary['parlamentarischer-staatssekretaer'],
    });
    expect(parts.filter((p) => p.entry)).toHaveLength(1);
  });

  it('explains a Gremium role', () => {
    expect(splitLabel('Obfrau', glossary)).toEqual([
      { text: 'Obfrau', entry: glossary.obmann },
    ]);
  });

  it('works without a glossary', () => {
    expect(splitLabel('Obfrau', {})).toEqual([{ text: 'Obfrau' }]);
  });
});
