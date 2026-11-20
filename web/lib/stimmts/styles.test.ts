import { describe, expect, it } from 'bun:test';
import {
  STYLES,
  STYLE_MILESTONES,
  effectiveStyle,
  freshStyles,
  isStyleId,
  unlockedStyles,
  visibleStyles,
} from './styles';

describe('unlockedStyles', () => {
  it('nothing but standard at 2 days', () => {
    expect(unlockedStyles(2, 6)).toEqual(['standard']);
  });

  it('papier at 3, kuppel at 5, nacht at 7, gold at 15', () => {
    expect(unlockedStyles(3, 6)).toContain('papier');
    expect(unlockedStyles(4, 6)).not.toContain('kuppel');
    expect(unlockedStyles(5, 6)).toContain('kuppel');
    expect(unlockedStyles(6, 6)).not.toContain('nacht');
    expect(unlockedStyles(7, 6)).toContain('nacht');
    expect(unlockedStyles(14, 6)).not.toContain('gold');
    expect(unlockedStyles(15, 6)).toContain('gold');
  });

  it('festlich only in December and from 15 days', () => {
    expect(unlockedStyles(15, 12)).toContain('festlich');
    expect(unlockedStyles(15, 1)).not.toContain('festlich');
    expect(unlockedStyles(14, 12)).not.toContain('festlich');
  });
});

describe('visibleStyles', () => {
  it('lists festlich sixth, after gold, in December only', () => {
    expect(visibleStyles(12)).toEqual([
      'standard',
      'papier',
      'kuppel',
      'nacht',
      'gold',
      'festlich',
    ]);
    expect(visibleStyles(11)).not.toContain('festlich');
  });
});

describe('effectiveStyle', () => {
  it('falls back to standard', () => {
    expect(effectiveStyle('festlich', 30, 1)).toBe('standard');
    expect(effectiveStyle('GOLD', 30, 6)).toBe('standard');
    expect(effectiveStyle('../x', 30, 6)).toBe('standard');
    expect(effectiveStyle(42, 30, 6)).toBe('standard');
    expect(effectiveStyle('gold', 14, 6)).toBe('standard');
  });

  it('keeps an unlocked choice', () => {
    expect(effectiveStyle('gold', 15, 6)).toBe('gold');
    expect(effectiveStyle('festlich', 15, 12)).toBe('festlich');
  });
});

describe('freshStyles', () => {
  it('never lists standard', () => {
    expect(freshStyles(['standard', 'papier'], [])).toEqual(['papier']);
    expect(freshStyles(['standard'], [])).toEqual([]);
    expect(freshStyles(['standard', 'papier'], ['papier'])).toEqual([]);
  });
});

describe('tables', () => {
  it('milestones match the unlock days', () => {
    expect(STYLE_MILESTONES).toEqual([3, 5, 7, 15]);
    expect(STYLES.map((style) => style.id)).toContain('festlich');
    expect(isStyleId('papier')).toBe(true);
    expect(isStyleId('nope')).toBe(false);
  });
});
