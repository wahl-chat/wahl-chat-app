import { describe, expect, test } from 'bun:test';
import {
  barFill,
  barLabel,
  gridColumns,
  milestoneMarks,
  nextIndex,
  styleButtonLabel,
  thumbLabel,
  thumbSubline,
} from './style-sheet-view';

describe('thumbSubline', () => {
  test('says when a style comes or that it is always there', () => {
    expect(thumbSubline('standard', 0)).toBe('immer');
    expect(thumbSubline('papier', 2)).toBe('ab 3 Tagen');
    expect(thumbSubline('papier', 3)).toBe('3 Tage');
    expect(thumbSubline('gold', 14)).toBe('ab 15 Tagen');
  });
});

describe('thumbLabel', () => {
  test('names the lock and the news', () => {
    expect(thumbLabel('nacht', 2, false)).toBe('Nacht, ab 7 Tagen');
    expect(thumbLabel('papier', 3, true)).toBe('Papier, neu');
    expect(thumbLabel('standard', 0, false)).toBe('Standard');
  });
});

describe('bar', () => {
  test('fills to the days played and stops at the end', () => {
    expect(barFill(0)).toBe(0);
    expect(barFill(3)).toBe(20);
    expect(barFill(40)).toBe(100);
  });

  test('marks sit at their day and light up once reached', () => {
    const marks = milestoneMarks(5);
    expect(marks.map((m) => m.days)).toEqual([3, 5, 7, 15]);
    expect(marks.map((m) => m.reached)).toEqual([true, true, false, false]);
    expect(marks[3]?.at).toBe(100);
  });

  test('label reads as the board has it', () => {
    expect(barLabel(8)).toBe('8 von 15 Tagen. Stile bei 3, 5, 7 und 15 Tagen');
  });
});

describe('gridColumns', () => {
  test('three columns for six thumbs, five otherwise', () => {
    expect(gridColumns(5)).toBe(5);
    expect(gridColumns(6)).toBe(3);
  });
});

describe('nextIndex', () => {
  test('wraps and ignores other keys', () => {
    expect(nextIndex(4, 'ArrowRight', 5)).toBe(0);
    expect(nextIndex(0, 'ArrowLeft', 5)).toBe(4);
    expect(nextIndex(1, 'End', 5)).toBe(4);
    expect(nextIndex(1, 'Tab', 5)).toBeNull();
  });
});

describe('styleButtonLabel', () => {
  test('announces a new style', () => {
    expect(styleButtonLabel(true)).toBe(
      'Stil ändern. Neuer Stil freigeschaltet',
    );
    expect(styleButtonLabel(false)).toBe('Stil ändern');
  });
});
