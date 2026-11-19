import { describe, expect, it } from 'bun:test';
import { PUZZLES, PUZZLE_COUNT, puzzleTitle } from '@/lib/stimmts/content';
import { parseShareParams } from '@/lib/stimmts/share-image';
import { renderToStaticMarkup } from 'react-dom/server';
import ShareImage, { SHARE_IMAGE_TEXT } from './share-image';

/** The image's markup for a request, with the title looked up as the route does. */
function drawn(query: string): string {
  const data = parseShareParams(
    new URLSearchParams(query),
    PUZZLE_COUNT,
    '2026-11-19',
  );
  if (!data) {
    throw new Error(`refused: ${query}`);
  }
  const result = data.result && {
    ...data.result,
    title: puzzleTitle(data.result.number) ?? undefined,
  };
  return renderToStaticMarkup(
    <ShareImage format={data.format} result={result} />,
  );
}

describe('ShareImage', () => {
  it("names the shared day's vote", () => {
    const markup = drawn('f=link&n=1&s=4&d=2026-11-15');
    expect(markup).toContain('Tankrabatt für Benzin und Diesel');
    expect(markup).toContain('4 von 5');
  });

  it('shows the title on the square too', () => {
    expect(drawn('f=square&n=1&s=4&d=2026-11-15')).toContain(
      'Tankrabatt für Benzin und Diesel',
    );
  });

  it("shows the game's own card without a result", () => {
    const markup = drawn('f=link');
    expect(markup).toContain('Wie haben die Parteien im Bundestag abgestimmt?');
    expect(markup).not.toContain('Tankrabatt');
  });
});

describe('SHARE_IMAGE_TEXT', () => {
  it('holds every character of every puzzle title, so the fonts can draw it', () => {
    const missing = new Set(
      PUZZLES.flatMap((puzzle) => [...puzzle.title]).filter(
        (char) => !SHARE_IMAGE_TEXT.includes(char),
      ),
    );
    expect([...missing]).toEqual([]);
  });
});
