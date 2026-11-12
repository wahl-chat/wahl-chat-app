import { describe, expect, it } from 'bun:test';
import type { DigestPartyPosition } from '@/lib/firebase/firebase.types';
import { feedLogoId, speakerLogoId, speakerPartyLabel } from './party-logos';

const position = (party_id: string, logo_id?: string): DigestPartyPosition => ({
  party_id,
  party_name: party_id,
  color: '#000000',
  logo_id,
  speakers: [],
  position: null,
});

describe('feedLogoId', () => {
  it('shows the Union logo for the Bundestag Fraktion only', () => {
    expect(feedLogoId('bundestag', 'cdu')).toBe('cdu_csu');
    expect(feedLogoId('bundestag', 'spd')).toBe('spd');
    // In a Landtag the CDU stands alone.
    expect(feedLogoId('landtag_st', 'cdu')).toBe('cdu');
  });
});

describe('speakerLogoId', () => {
  const union = position('cdu', 'cdu_csu');

  it('shows a Union speaker under their own party', () => {
    expect(speakerLogoId(union, 'CDU')).toBe('cdu');
    expect(speakerLogoId(union, ' csu ')).toBe('csu');
  });

  it('shows the Union logo until the record says which', () => {
    expect(speakerLogoId(union)).toBe('cdu_csu');
    expect(speakerLogoId(union, null)).toBe('cdu_csu');
  });

  it('keeps every other Fraktion logo', () => {
    expect(speakerLogoId(position('gruene'), 'BÜNDNIS 90/DIE GRÜNEN')).toBe(
      'gruene',
    );
    expect(speakerLogoId(position('cdu'), 'CSU')).toBe('cdu');
  });
});

describe('speakerPartyLabel', () => {
  const union = { ...position('cdu', 'cdu_csu'), party_name: 'CDU/CSU' };

  it('names the party the badge shows', () => {
    expect(speakerPartyLabel(union, 'CSU')).toBe('CSU');
    expect(speakerPartyLabel(union)).toBe('CDU/CSU');
    expect(
      speakerPartyLabel(
        { ...position('gruene'), party_name: 'Die Grünen' },
        'BÜNDNIS 90/DIE GRÜNEN',
      ),
    ).toBe('Die Grünen');
  });
});
