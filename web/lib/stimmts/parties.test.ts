import { describe, expect, it } from 'bun:test';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { PUZZLES } from './content';
import { partyFillClass, partyLogo, partyTileClass } from './parties';

const PUBLIC_DIR = join(import.meta.dir, '../../public');

describe('party assets', () => {
  const partyIds = new Set(
    PUZZLES.flatMap((puzzle) => puzzle.parties.map((party) => party.partyId)),
  );

  it.each([...partyIds])('has a logo file and a colour for %s', (partyId) => {
    expect(existsSync(join(PUBLIC_DIR, partyLogo(partyId)))).toBe(true);
    expect(partyTileClass(partyId)).toBe(`bg-party-${partyId}`);
    expect(partyFillClass(partyId)).toBe(`fill-party-${partyId}`);
  });

  it('uses the trimmed Die Linke wordmark, not the app-wide file', () => {
    expect(partyLogo('linke')).toBe('/images/stimmts/linke.png');
  });

  it('falls back to neutral colours for an unknown party', () => {
    expect(partyTileClass('bsw')).toBe('bg-muted');
    expect(partyFillClass('bsw')).toBe('fill-muted');
  });
});
