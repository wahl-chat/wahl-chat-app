import type { GlossaryEntry, TermRef } from '@/lib/firebase/firebase.types';

export type GlossaryIndex = Record<string, GlossaryEntry>;

/** A piece of text: plain, or a term the glossary explains. */
export type TextPart = { text: string; entry?: GlossaryEntry };

const WORD_CHAR = /[\p{L}\p{N}]/u;

/** Where `needle` stands in `text` as whole words, from `from` on; -1 if
 * nowhere. "Stunde" is not found inside "Stundenlohn". */
function wholeWordIndex(text: string, needle: string, from = 0): number {
  let at = text.indexOf(needle, from);
  while (at !== -1) {
    const before = at > 0 ? text[at - 1] : '';
    const after = text[at + needle.length] ?? '';
    if (!WORD_CHAR.test(before) && !WORD_CHAR.test(after)) {
      return at;
    }
    at = text.indexOf(needle, at + 1);
  }
  return -1;
}

type Match = { start: number; end: number; entry: GlossaryEntry };

/** The text split at the first occurrence of each term, longest first so
 * "Parlamentarische Staatssekretärin" wins over "Staatssekretärin". A term
 * appears once per text: underlining every repeat reads as noise. */
function split(
  text: string,
  candidates: { surface: string; entry: GlossaryEntry }[],
): TextPart[] {
  const matches: Match[] = [];
  const seen = new Set<string>();
  const ordered = [...candidates].sort(
    (a, b) => b.surface.length - a.surface.length,
  );
  for (const { surface, entry } of ordered) {
    if (seen.has(entry.term_id)) {
      continue;
    }
    let at = wholeWordIndex(text, surface);
    while (
      at !== -1 &&
      matches.some((m) => at < m.end && at + surface.length > m.start)
    ) {
      at = wholeWordIndex(text, surface, at + 1);
    }
    if (at !== -1) {
      matches.push({ start: at, end: at + surface.length, entry });
      seen.add(entry.term_id);
    }
  }
  matches.sort((a, b) => a.start - b.start);
  const parts: TextPart[] = [];
  let cursor = 0;
  for (const match of matches) {
    if (match.start > cursor) {
      parts.push({ text: text.slice(cursor, match.start) });
    }
    parts.push({
      text: text.slice(match.start, match.end),
      entry: match.entry,
    });
    cursor = match.end;
  }
  if (cursor < text.length) {
    parts.push({ text: text.slice(cursor) });
  }
  return parts;
}

/** An item's text with the terms the feed job found in it. */
export function splitByRefs(
  text: string,
  refs: TermRef[],
  glossary: GlossaryIndex,
): TextPart[] {
  const candidates = refs.flatMap((ref) => {
    const entry = glossary[ref.term_id];
    return entry ? [{ surface: ref.surface, entry }] : [];
  });
  return candidates.length > 0 ? split(text, candidates) : [{ text }];
}

/** An office, a Gremium or a role in it ("Parlamentarische Staatssekretärin
 * beim …", "Der Ältestenrat", "Obfrau") with the glossary terms it contains.
 * These are a small closed vocabulary, so they are matched against every
 * stored form. */
export function splitLabel(label: string, glossary: GlossaryIndex): TextPart[] {
  const candidates = Object.values(glossary).flatMap((entry) =>
    entry.forms.map((surface) => ({ surface, entry })),
  );
  return candidates.length > 0 ? split(label, candidates) : [{ text: label }];
}
