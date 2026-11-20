import { describe, expect, it } from 'bun:test';
import { TANKRABATT_PUZZLE } from '@/lib/stimmts/fixtures';
import { renderToStaticMarkup } from 'react-dom/server';
import VoteResultCard from './vote-result-card';

const markup = renderToStaticMarkup(
  <VoteResultCard puzzle={TANKRABATT_PUZZLE} onOpen={() => {}} />,
);

describe('VoteResultCard', () => {
  it('heads the card with the topic and the kind of vote', () => {
    expect(markup).toContain('Energie · Namentliche Abstimmung');
    expect(markup).toContain('Tankrabatt für Benzin und Diesel');
  });

  it('carries the outcome as the feed badge', () => {
    expect(markup).toContain('Angenommen');
  });

  it('counts the whole Bundestag under the chamber', () => {
    for (const label of [
      '433 Ja',
      '127 Nein',
      '0 Enthalten',
      '67 Nicht beteiligt',
    ]) {
      expect(markup).toContain(label);
    }
  });

  it('links its source', () => {
    expect(markup).toContain(TANKRABATT_PUZZLE.source.url);
  });

  it('shows Abgeordnetenwatch by its logo, in both variants', () => {
    expect(markup).toContain('Quelle');
    expect(markup).not.toContain('Quelle: ');
    expect(markup).toContain('abgeordnetenwatch.png');
    expect(markup).toContain('abgeordnetenwatch-dark.png');
  });

  it('names any other source', () => {
    const other = renderToStaticMarkup(
      <VoteResultCard
        puzzle={{
          ...TANKRABATT_PUZZLE,
          source: { label: 'Bundestag', url: 'https://www.bundestag.de/x' },
        }}
        onOpen={() => {}}
      />,
    );
    expect(other).toContain('Quelle: Bundestag');
    expect(other).not.toContain('abgeordnetenwatch.png');
  });
});
