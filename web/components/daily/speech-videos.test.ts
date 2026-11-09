import { describe, expect, it } from 'bun:test';
import type { DigestSessionSection } from '@/lib/firebase/firebase.types';
import { sectionMedia } from './speech-videos';

const SECTION: DigestSessionSection = {
  topic: 'wirtschaft',
  headline: 'Wohnungsbau',
  summary: '',
  agenda_items: ['TOP 1'],
  citations: [],
  video_url: 'https://video/agenda.mp4#t=12',
};

describe('sectionMedia', () => {
  it('plays from the second the poster shows', () => {
    const media = sectionMedia({
      ...SECTION,
      card_video: {
        video_url: 'https://video/a.mp4',
        start: 83.5,
        poster_url: 'https://posters/a.jpg',
        speaker: 'Anna',
        party_name: 'SPD',
      },
    });
    expect(media?.src).toBe('https://video/a.mp4#t=83.5');
    expect(media?.poster).toBe('https://posters/a.jpg');
    expect(media?.caption).toBe('Anna (SPD) · ab 1:23');
  });

  it('names the speaker without a start time near the beginning', () => {
    const media = sectionMedia({
      ...SECTION,
      card_video: {
        video_url: 'https://video/a.mp4',
        start: 0.5,
        poster_url: null,
        speaker: 'Clara',
        party_name: null,
      },
    });
    expect(media?.caption).toBe('Clara');
    expect(media?.poster).toBeNull();
  });

  it('falls back to the agenda video without a poster or a choice of its own', () => {
    const media = sectionMedia(SECTION);
    expect(media?.src).toBe('https://video/agenda.mp4#t=0.5');
    expect(media?.poster).toBeNull();
    expect(media?.caption).toBeNull();
    expect(sectionMedia({ ...SECTION, video_url: null })).toBeNull();
  });

  it('keeps a local preview audio summary', () => {
    const media = sectionMedia({
      ...SECTION,
      audio: { title: 'Kurz gehört', url: 'https://audio/a.mp3' },
    });
    expect(media?.kind).toBe('audio');
    expect(media?.caption).toBe('Kurz gehört');
  });
});
