import { describe, expect, it } from 'bun:test';
import { shareChallenge } from './challenge';

const TODAY = '2026-11-19';
const challenge = (search: string, playedToday = false) =>
  shareChallenge({ search, today: TODAY, playedToday });

describe('shareChallenge', () => {
  it('challenges the friend to beat the shared score', () => {
    expect(challenge('?n=5&s=4&d=2026-11-19')).toBe(
      'Schaffst du mehr als 4/5?',
    );
    expect(challenge('?n=5&s=0&d=2026-11-19')).toBe(
      'Schaffst du mehr als 0/5?',
    );
  });

  it('asks to match a perfect score, which cannot be beaten', () => {
    expect(challenge('?n=5&s=5&d=2026-11-19')).toBe('Schaffst du auch 5/5?');
  });

  it('stays quiet for another day, which is a different puzzle', () => {
    expect(challenge('?n=5&s=4&d=2026-11-18')).toBeNull();
  });

  it('refuses a score out of range', () => {
    expect(challenge('?n=5&s=9&d=2026-11-19')).toBeNull();
  });

  it('stays quiet once the visitor has played today', () => {
    expect(challenge('?n=5&s=4&d=2026-11-19', true)).toBeNull();
  });

  it('stays quiet without a shared result', () => {
    expect(challenge('')).toBeNull();
    expect(challenge('?f=link')).toBeNull();
  });
});
