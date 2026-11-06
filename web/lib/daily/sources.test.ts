import { describe, expect, it } from 'bun:test';
import type {
  DigestSessionSection,
  SpeechSource,
} from '@/lib/firebase/firebase.types';
import {
  isVideoSource,
  numberedSources,
  sourceTooltip,
  toViewerSource,
} from './sources';

const PDF = 'https://dserver.bundestag.de/btp/21/21090.pdf';

const source = (over: Partial<SpeechSource>): SpeechSource => ({
  speaker: 'Anna',
  party_id: 'spd',
  party_name: 'SPD',
  video_url: 'https://video/a.mp4',
  start: 83.5,
  pdf_url: PDF,
  page: 12,
  snippet: 'Wir brauchen mehr Wohnungen.',
  ...over,
});

const ANNA = source({});
const BERND = source({
  speaker: 'Bernd',
  party_id: 'csu',
  party_name: 'CSU',
  video_url: null,
  start: null,
  page: 14,
  snippet: 'Erst die Kosten prüfen.',
});

const section = (
  over: Partial<DigestSessionSection>,
): DigestSessionSection => ({
  topic: 'housing_rent',
  headline: 'Wohnungsbau',
  summary: '',
  agenda_items: [],
  citations: [],
  video_url: null,
  ...over,
});

const position = (
  party_id: string,
  text: string | null,
  sources: SpeechSource[],
) => ({
  party_id,
  party_name: party_id,
  color: '#000',
  speakers: [],
  position: text,
  sources,
});

describe('numberedSources', () => {
  it('numbers each passage once, bullets first, then positions as listed', () => {
    const numbered = numberedSources(
      section({
        key_point_sources: [[ANNA], [], [ANNA, BERND]],
        positions: [
          position('spd', 'Fordern mehr.', [ANNA]),
          position('cdu', 'Wollen prüfen.', [BERND, { ...ANNA, start: 4 }]),
        ],
      }),
      ['cdu', 'spd'],
    );
    expect(numbered.sources).toHaveLength(3);
    expect([0, 1, 2].map(numbered.keyPoint)).toEqual([[1], [], [1, 2]]);
    expect(numbered.position('cdu')).toEqual([2, 3]);
    expect(numbered.position('spd')).toEqual([1]);
  });

  it('cites nothing for a Fraktion without a sentence or an older item', () => {
    const numbered = numberedSources(
      section({ positions: [position('afd', null, [ANNA])] }),
      ['afd'],
    );
    expect(numbered.position('afd')).toEqual([]);
    expect(numbered.keyPoint(0)).toEqual([]);
    expect(numbered.sources).toEqual([]);
  });
});

describe('toViewerSource', () => {
  it('opens the video at the passage when the speech has one', () => {
    const target = toViewerSource(ANNA);
    expect(target.video_url).toBe('https://video/a.mp4#t=83.5');
    expect(target.pdf_url).toBeUndefined();
    expect(isVideoSource(ANNA)).toBe(true);
  });

  it('opens the protocol at its page with the sentence otherwise', () => {
    const target = toViewerSource(BERND);
    expect(target.video_url).toBeUndefined();
    expect([target.pdf_url, target.page, target.snippet]).toEqual([
      PDF,
      14,
      'Erst die Kosten prüfen.',
    ]);
    expect(isVideoSource(BERND)).toBe(false);
  });
});

describe('sourceTooltip', () => {
  it('names the speaker and where the passage is', () => {
    expect(sourceTooltip(ANNA)).toBe('Anna (SPD) · ab 1:23');
    expect(sourceTooltip(BERND)).toBe('Bernd (CSU) · Plenarprotokoll S. 14');
    expect(sourceTooltip({ ...BERND, page: null })).toBe(
      'Bernd (CSU) · Plenarprotokoll',
    );
  });
});
