import { describe, expect, it } from 'bun:test';
import { PUZZLES, PUZZLE_COUNT, puzzleTitle } from '@/lib/stimmts/content';
import { parseShareParams } from '@/lib/stimmts/share-image';
import { STYLES, type StyleId } from '@/lib/stimmts/styles';
import {
  Fragment,
  type ReactElement,
  type ReactNode,
  isValidElement,
} from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import ShareImage, { SHARE_IMAGE_TEXT } from './share-image';

/** The image for a request, with the title looked up as the route does. */
function image(query: string, style?: StyleId): ReactElement {
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
  return <ShareImage format={data.format} result={result} style={style} />;
}

function drawn(query: string, style?: StyleId): string {
  return renderToStaticMarkup(image(query, style));
}

function Shape() {
  return <circle />;
}

type Props = { children?: ReactNode };

/**
 * Components and fragments found inside an svg, expanding components
 * outside one as next/og does.
 */
function svgProblems(node: ReactNode, inSvg = false): string[] {
  if (Array.isArray(node)) {
    return node.flatMap((child) => svgProblems(child, inSvg));
  }
  if (!isValidElement<Props>(node)) {
    return [];
  }
  const { type, props } = node;
  if (typeof type === 'function') {
    return inSvg
      ? [type.name]
      : svgProblems((type as (p: Props) => ReactNode)(props), false);
  }
  // ReactElement's type does not include fragments, though they are elements.
  if ((type as unknown) === Fragment) {
    return inSvg ? ['fragment'] : svgProblems(props.children, false);
  }
  return svgProblems(props.children, inSvg || type === 'svg');
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

describe('styles', () => {
  const QUERIES = [
    'f=square&n=1&s=4&d=2026-11-15&p=4',
    'f=story&n=2&s=0&d=2026-11-16&p=x0',
    'f=link&n=1&s=5&d=2026-11-15',
  ];

  it.each(STYLES.map((style) => [style.id]))(
    'renders with every style without throwing: %s',
    (style) => {
      for (const query of QUERIES) {
        expect(drawn(query, style)).toContain('wahl.chat/stimmts');
      }
    },
  );

  it('puts only plain elements inside every svg, as next/og needs', () => {
    // next/og never calls a component or unwraps a fragment inside an svg:
    // such a shape is silently left out of the PNG.
    expect(
      svgProblems(
        <svg>
          <Shape />
          {/* biome-ignore lint/complexity/noUselessFragments: the case under test. */}
          <></>
        </svg>,
      ),
    ).toEqual(['Shape', 'fragment']);
    for (const { id } of STYLES) {
      for (const query of QUERIES) {
        expect(svgProblems(image(query, id))).toEqual([]);
      }
    }
  });

  it('draws each style differently from the standard', () => {
    for (const { id } of STYLES.filter((style) => style.id !== 'standard')) {
      expect(drawn(QUERIES[0], id)).not.toBe(drawn(QUERIES[0]));
    }
  });

  it('keeps the seat colours on every style', () => {
    for (const { id } of STYLES) {
      const markup = drawn(QUERIES[0], id);
      for (const seat of ['#2f8a5b', '#c2414b', '#d9a93a']) {
        expect(markup).toContain(seat);
      }
    }
  });
});

describe('the standard style', () => {
  it.each([
    'f=square&n=1&s=4&d=2026-11-15&p=4',
    'f=story&n=2&s=0&d=2026-11-16&p=x0',
    'f=link&n=1&s=5&d=2026-11-15',
    'f=link',
  ])('standard output is unchanged: %s', (query) => {
    expect(drawn(query)).toMatchSnapshot();
    expect(drawn(query, 'standard')).toBe(drawn(query));
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
