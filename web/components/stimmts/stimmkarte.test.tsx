import { describe, expect, it } from 'bun:test';
import { renderToStaticMarkup } from 'react-dom/server';
import Stimmkarte from './stimmkarte';

const CARD = {
  number: 1,
  playDate: '2026-11-15',
  title: 'Tankrabatt für Benzin und Diesel',
  topic: 'Energie',
};

describe('Stimmkarte', () => {
  it("keeps a played past day's title as the page heading", () => {
    const markup = renderToStaticMarkup(<Stimmkarte {...CARD} score={4} />);
    expect(markup).toContain('<h1');
    expect(markup).toMatch(/<h1[^>]*>Tankrabatt für Benzin und Diesel<\/h1>/);
  });

  it('names the card to be cast by its day and score', () => {
    const markup = renderToStaticMarkup(
      <Stimmkarte {...CARD} score={4} onCast={() => {}} />,
    );
    expect(markup).toContain(
      'aria-label="Stimmkarte vom 15. November, 4 von 5 richtig. In die Urne werfen"',
    );
    expect(markup).not.toContain('<h1');
  });
});
