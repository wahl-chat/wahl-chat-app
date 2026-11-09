import type {
  DigestSessionSection,
  SpeechSource,
} from '@/lib/firebase/firebase.types';
import type { Source } from '@/lib/stores/chat-store.types';
import { formatTimestamp } from '@/lib/utils';

/** A debate's sources, numbered once each in reading order, so the same
 * passage cited by a bullet and a position carries one number. */
export type NumberedSources = {
  /** Source `n` is `sources[n - 1]`. */
  sources: SpeechSource[];
  keyPoint: (index: number) => number[];
  position: (partyId: string) => number[];
};

function sourceKey(source: SpeechSource): string {
  return [
    source.speaker,
    source.video_url ?? source.pdf_url,
    source.start ?? source.page,
    source.snippet,
  ].join('|');
}

/** Numbers the bullets' sources first, then the positions' in the order the
 * detail view lists the Fraktionen. */
export function numberedSources(
  section: DigestSessionSection,
  partyOrder: readonly string[],
): NumberedSources {
  const sources: SpeechSource[] = [];
  const numbers = new Map<string, number>();
  const number = (source: SpeechSource): number => {
    const key = sourceKey(source);
    let n = numbers.get(key);
    if (n === undefined) {
      sources.push(source);
      n = sources.length;
      numbers.set(key, n);
    }
    return n;
  };
  const numberAll = (list: readonly SpeechSource[] | undefined) => [
    ...new Set((list ?? []).map(number)),
  ];

  const keyPoints = (section.key_point_sources ?? []).map(numberAll);
  const byParty = new Map(
    (section.positions ?? []).map((p) => [p.party_id, p] as const),
  );
  const positions = new Map(
    partyOrder.map((partyId) => {
      const position = byParty.get(partyId);
      // A Fraktion without a position sentence has nothing to cite.
      return [partyId, position?.position ? numberAll(position.sources) : []];
    }),
  );
  return {
    sources,
    keyPoint: (index) => keyPoints[index] ?? [],
    position: (partyId) => positions.get(partyId) ?? [],
  };
}

function speakerLabel(source: SpeechSource): string {
  return `${source.speaker} (${source.party_name})`;
}

function videoLink(source: SpeechSource): string | null {
  if (!source.video_url) {
    return null;
  }
  return source.start !== null && source.start !== undefined
    ? `${source.video_url}#t=${source.start}`
    : source.video_url;
}

/** What the media viewer opens: the video at the passage when there is one,
 * else the protocol at its page with the sentence highlighted. */
export function toViewerSource(source: SpeechSource): Source {
  const video = videoLink(source);
  const base = {
    source: speakerLabel(source),
    source_document: speakerLabel(source),
    document_publish_date: '',
    party_id: source.party_id,
    source_type: 'parliamentary_speech' as const,
  };
  if (video) {
    return { ...base, url: video, video_url: video, page: 1 };
  }
  return {
    ...base,
    url: source.pdf_url ?? '',
    pdf_url: source.pdf_url ?? undefined,
    page: source.page ?? 1,
    snippet: source.snippet ?? undefined,
  };
}

export function isVideoSource(source: SpeechSource): boolean {
  return Boolean(source.video_url);
}

/** "Name (Partei) · ab 1:23", or the protocol page without a video. */
export function sourceTooltip(source: SpeechSource): string {
  const who = speakerLabel(source);
  if (source.video_url) {
    return source.start !== null && source.start !== undefined
      ? `${who} · ab ${formatTimestamp(source.start)}`
      : `${who} · Video`;
  }
  return source.page
    ? `${who} · Plenarprotokoll S. ${source.page}`
    : `${who} · Plenarprotokoll`;
}
