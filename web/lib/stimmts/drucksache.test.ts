import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import {
  drucksachePdfUrl,
  keyPointSourceAria,
  keyPointSourceLabel,
  keyPointSourceUrl,
} from './drucksache';

describe('drucksachePdfUrl', () => {
  it('pads the number to five digits and files it by its first three', () => {
    expect(drucksachePdfUrl('21/8157')).toBe(
      'https://dserver.bundestag.de/btd/21/081/2108157.pdf',
    );
    expect(drucksachePdfUrl('21/6561')).toBe(
      'https://dserver.bundestag.de/btd/21/065/2106561.pdf',
    );
    expect(drucksachePdfUrl('21/134')).toBe(
      'https://dserver.bundestag.de/btd/21/001/2100134.pdf',
    );
  });

  it('reproduces every Drucksache URL in the shipped puzzles', () => {
    let checked = 0;
    for (const { document } of PUZZLES) {
      if (!document) continue;
      expect(drucksachePdfUrl(document.number)).toBe(document.url);
      checked += 1;
      if (document.votedIn) {
        expect(drucksachePdfUrl(document.votedIn.number)).toBe(
          document.votedIn.url,
        );
        checked += 1;
      }
    }
    expect(checked).toBeGreaterThan(0);
  });
});

describe('key point source', () => {
  it('links to the page in the PDF', () => {
    expect(keyPointSourceUrl({ document: '21/8157', page: 418 })).toBe(
      'https://dserver.bundestag.de/btd/21/081/2108157.pdf#page=418',
    );
  });

  it('labels the source for the chip', () => {
    expect(keyPointSourceLabel({ document: '21/8157', page: 4 })).toBe(
      '21/8157 · S. 4',
    );
  });

  it('spells the source out for screen readers', () => {
    expect(keyPointSourceAria({ document: '21/8157', page: 4 })).toBe(
      'Quelle: Drucksache 21/8157, Seite 4',
    );
  });
});
