import type { KeyPointSource } from './types';

const PDF_BASE = 'https://dserver.bundestag.de/btd';

/**
 * The Bundestag files each Drucksache under its Wahlperiode and the first
 * three digits of its number zero-padded to five, so the link can be built
 * from the number alone instead of being stored beside every source.
 */
export function drucksachePdfUrl(number: string): string {
  const [period, serial] = number.split('/');
  const padded = serial.padStart(5, '0');
  return `${PDF_BASE}/${period}/${padded.slice(0, 3)}/${period}${padded}.pdf`;
}

/** `#page=N` opens the PDF viewer on the page that backs the key point. */
export function keyPointSourceUrl(source: KeyPointSource): string {
  return `${drucksachePdfUrl(source.document)}#page=${source.page}`;
}

export function keyPointSourceLabel(source: KeyPointSource): string {
  return `${source.document} · S. ${source.page}`;
}

export function keyPointSourceAria(source: KeyPointSource): string {
  return `Quelle: Drucksache ${source.document}, Seite ${source.page}`;
}
