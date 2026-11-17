import { describe, expect, it } from 'bun:test';
import type { PartyDetails } from '@/lib/party-details';
import { focusLabel, focusStamp, toggleFocus } from './chat-focus';

const PARTIES = [
  { party_id: 'spd', name: 'SPD' },
  { party_id: 'cdu', name: 'CDU' },
] as PartyDetails[];

describe('focusStamp', () => {
  it('stamps the focus in order', () => {
    expect(focusStamp(new Set(['spd', 'cdu']))).toEqual({
      focus_party_ids: ['spd', 'cdu'],
    });
  });

  it('stamps nothing without a focus', () => {
    expect(focusStamp(new Set())).toEqual({});
  });
});

describe('focusLabel', () => {
  it('names the parties', () => {
    expect(focusLabel(['spd', 'cdu'], PARTIES)).toBe('SPD · CDU');
  });

  it('keeps an unknown id', () => {
    expect(focusLabel(['bsw'], PARTIES)).toBe('bsw');
    expect(focusLabel(['spd'], undefined)).toBe('spd');
  });
});

describe('toggleFocus', () => {
  it('adds and removes', () => {
    expect(toggleFocus(['spd'], 'cdu')).toEqual(['spd', 'cdu']);
    expect(toggleFocus(['spd', 'cdu'], 'spd')).toEqual(['cdu']);
  });
});
