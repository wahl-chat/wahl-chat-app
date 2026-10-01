import { describe, expect, it } from 'bun:test';
import type { DigestSessionSection } from '@/lib/firebase/firebase.types';
import {
  matchesTopics,
  otherTopicsSentence,
  parseTopicsParam,
  splitSections,
} from './topics';

function section(topic: string, headline: string): DigestSessionSection {
  return {
    topic,
    headline,
    summary: '',
    agenda_items: [],
    citations: [],
    video_url: null,
  };
}

const SECTIONS = [
  section('housing_rent', 'Mietpreisbremse'),
  section('health_care', 'Krankenhausreform'),
  section('economy_finance', 'Haushalt 2027'),
];

describe('matchesTopics', () => {
  it('treats an empty selection as everything', () => {
    expect(matchesTopics(['other'], [])).toBe(true);
  });

  it('matches when any item topic is selected', () => {
    expect(
      matchesTopics(['housing_rent', 'social_labor'], ['social_labor']),
    ).toBe(true);
    expect(matchesTopics(['housing_rent'], ['health_care'])).toBe(false);
  });
});

describe('splitSections + otherTopicsSentence', () => {
  it('names the filtered-out sections and the minor items', () => {
    const { visible, hidden } = splitSections(SECTIONS, ['health_care']);
    expect(visible.map((s) => s.headline)).toEqual(['Krankenhausreform']);
    expect(otherTopicsSentence(hidden, ['Wahl eines Schriftführers'])).toBe(
      'Außerdem ging es um Mietpreisbremse, Haushalt 2027 und Wahl eines Schriftführers.',
    );
  });

  it('still closes with the minor items when nothing is filtered out', () => {
    const { hidden } = splitSections(SECTIONS, []);
    expect(hidden).toEqual([]);
    expect(otherTopicsSentence(hidden, ['Fragestunde'])).toBe(
      'Außerdem ging es um Fragestunde.',
    );
  });

  it('always yields a closing sentence', () => {
    expect(otherTopicsSentence([], [])).toContain('Weitere Themen');
  });

  it('does not repeat a name', () => {
    expect(
      otherTopicsSentence([section('other', 'Fragestunde')], ['Fragestunde']),
    ).toBe('Außerdem ging es um Fragestunde.');
  });
});

describe('parseTopicsParam', () => {
  it('keeps known topics once and drops the rest', () => {
    expect(parseTopicsParam('housing_rent,nope,housing_rent,other')).toEqual([
      'housing_rent',
      'other',
    ]);
    expect(parseTopicsParam(undefined)).toEqual([]);
  });
});
