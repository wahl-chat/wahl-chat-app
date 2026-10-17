import { describe, expect, it } from 'bun:test';
import type { DigestSessionSection } from '@/lib/firebase/firebase.types';
import { openingParty } from './items';

const SECTION: DigestSessionSection = {
  topic: 'economy_finance',
  headline: '',
  summary: '',
  agenda_items: [],
  citations: [],
  video_url: null,
};

describe('openingParty', () => {
  it('prefers the recorded opener', () => {
    expect(openingParty({ ...SECTION, opened_by: 'spd' })).toBe('spd');
  });

  it('falls back to the first cited speech, mapped to its Fraktion', () => {
    const citations = [{ title: '', url: '', party_id: 'csu' }];
    expect(openingParty({ ...SECTION, citations })).toBe('cdu');
  });

  it('is null when nothing says who opened', () => {
    expect(openingParty(SECTION)).toBeNull();
  });
});
