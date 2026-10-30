import { describe, expect, it } from 'bun:test';
import { LOCALES } from '@/i18n/locales';
import de from './de';
import en from './en';

// Every locale's catalog, keyed like LOCALES. A new language that is in the
// registry but not here fails the first test.
const CATALOGS: Record<string, unknown> = { de, en };

type Tree = { [key: string]: string | Tree };

/** `{ 'feed.seat.yes': 'Ja', … }` */
function flatten(tree: Tree, prefix = ''): Record<string, string> {
  return Object.entries(tree).reduce<Record<string, string>>(
    (flat, [key, value]) => {
      const path = prefix ? `${prefix}.${key}` : key;
      return typeof value === 'string'
        ? Object.assign(flat, { [path]: value })
        : Object.assign(flat, flatten(value, path));
    },
    {},
  );
}

/** ICU argument names: `{name}`, `{count, plural, …}`. */
function argumentNames(message: string): string[] {
  return [
    ...new Set(
      [...message.matchAll(/\{\s*([A-Za-z_][\w]*)\s*[,}]/g)].map((m) => m[1]),
    ),
  ].sort();
}

const source = flatten(de as unknown as Tree);

describe('message catalogs', () => {
  it('exist for every locale in the registry', () => {
    expect(Object.keys(CATALOGS).sort()).toEqual([...LOCALES].sort());
  });

  for (const locale of LOCALES.filter((l) => l !== 'de')) {
    const target = flatten(CATALOGS[locale] as Tree);

    it(`${locale} has exactly the German keys`, () => {
      expect(Object.keys(target).sort()).toEqual(Object.keys(source).sort());
    });

    it(`${locale} keeps every placeholder of the German message`, () => {
      const mismatches = Object.entries(source)
        .filter(([key]) => key in target)
        .filter(
          ([key, message]) =>
            argumentNames(message).join() !== argumentNames(target[key]).join(),
        )
        .map(([key]) => key);
      expect(mismatches).toEqual([]);
    });

    it(`${locale} has no empty messages`, () => {
      expect(
        Object.entries(target)
          .filter(([, message]) => !message.trim())
          .map(([key]) => key),
      ).toEqual([]);
    });
  }
});
