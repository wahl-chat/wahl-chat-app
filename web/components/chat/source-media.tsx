'use client';

import { ChatMessageIcon } from '@/components/chat/chat-message-icon';
import { Button } from '@/components/ui/button';
import type { Source } from '@/lib/stores/chat-store.types';
import {
  type SourceMediaLink,
  cn,
  formatGermanDate,
  getSourceMediaLinks,
  isProxyablePdfHost,
  pdfProxyUrl,
  sourceBadgeLabel,
  videoTimestampSeconds,
} from '@/lib/utils';
import {
  ArrowLeftIcon,
  ExternalLinkIcon,
  FileTextIcon,
  Loader2Icon,
  PlayIcon,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

export type ActiveMedia = {
  kind: 'video' | 'pdf';
  url: string;
  title: string;
  /** 1-based PDF page to open at (e.g. an AW Wahlprogramm page citation). */
  page?: number;
  /** Verbatim phrase to jump to / highlight via the viewer's `#search=` param. */
  search?: string;
};

/**
 * True when the current device should view PDFs in-page (fine pointer / desktop).
 * On coarse-pointer (touch) devices in-page PDF <iframe>s are unreliable — iOS
 * Safari commonly renders them blank — so those open in a new tab instead.
 */
function prefersInPagePdf(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) {
    return true;
  }
  return window.matchMedia('(pointer: fine)').matches;
}

function openExternally(url: string): void {
  window.open(url, '_blank', 'noopener,noreferrer');
}

/**
 * PDF open-parameter fragment for native browser viewers: `#page=N` (exact, only
 * when N > 1) plus a best-effort `#search=<phrase>` that jumps to and highlights the
 * cited passage. Both degrade gracefully — an unsupported viewer just ignores them.
 */
function pdfFragment(page?: number, search?: string): string {
  const params: string[] = [];
  if (page && page > 1) {
    params.push(`page=${page}`);
  }
  if (search) {
    params.push(`search=${encodeURIComponent(search)}`);
  }
  return params.length > 0 ? `#${params.join('&')}` : '';
}

/** Same-origin proxied PDF URL to frame, deep-linked to `page`/`search` when known. */
function pdfViewerSrc(url: string, page?: number, search?: string): string {
  return `${pdfProxyUrl(url)}${pdfFragment(page, search)}`;
}

/**
 * Decide how a source's format link opens: the in-page viewer (videos always;
 * PDFs on the proxy allowlist AND on a device where in-page PDFs are reliable)
 * or a new tab (off-allowlist PDFs, touch devices, plain weblinks). PDF page
 * citations carry their `page` through to both paths.
 */
function resolveMediaOpen(
  link: SourceMediaLink,
  source: Source,
): { viewer: ActiveMedia } | { newTab: string } {
  const title = source.source;
  if (link.kind === 'video') {
    return { viewer: { kind: 'video', url: link.url, title } };
  }
  if (isProxyablePdfHost(link.url) && prefersInPagePdf()) {
    return {
      viewer: {
        kind: 'pdf',
        url: link.url,
        title,
        page: source.page,
        search: source.snippet,
      },
    };
  }
  // New tab (off-allowlist / touch): keep the page + highlight anchors on the raw URL.
  return { newTab: `${link.url}${pdfFragment(source.page, source.snippet)}` };
}

/**
 * Open a source's primary format the same way a source row does — in the in-page
 * viewer when embeddable, else a new tab. Shared by the sources list AND the
 * in-text citation pills so a citation click behaves identically to the list.
 */
export function openSourceMedia(
  source: Source,
  onOpenMedia: (media: ActiveMedia) => void,
): void {
  const links = getSourceMediaLinks(source);
  if (links.length > 0) {
    const resolved = resolveMediaOpen(links[0], source);
    if ('viewer' in resolved) {
      onOpenMedia(resolved.viewer);
    } else {
      openExternally(resolved.newTab);
    }
  } else if (source.url) {
    // Plain weblink (no embeddable media) — open externally.
    openExternally(`${source.url}${pdfFragment(source.page, source.snippet)}`);
  }
}

/**
 * The in-page media view that replaces the sources list inside the "Quellen"
 * dialog: a native <video> for speech deep-links (seeks to the cited moment via
 * `#t=`) or an <iframe> of the same-origin PDF proxy for documents. A "Neuer Tab"
 * escape hatch is always available, and a load failure shows an explicit
 * fallback instead of a silent blank box.
 */
export function SourceMediaViewer({
  media,
  onBack,
}: {
  media: ActiveMedia;
  onBack: () => void;
}) {
  const backRef = useRef<HTMLButtonElement>(null);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // Move focus to "Zurück" when the viewer opens so keyboard/screen-reader users
  // land in the new view rather than on the dialog body.
  useEffect(() => {
    backRef.current?.focus();
  }, []);

  const seekSeconds =
    media.kind === 'video' ? videoTimestampSeconds(media.url) : null;

  // "Neuer Tab" opens the same anchored location as the in-page frame for PDFs.
  const externalHref =
    media.kind === 'pdf'
      ? `${media.url}${pdfFragment(media.page, media.search)}`
      : media.url;

  return (
    <div className="flex min-h-0 grow flex-col">
      {/* pr-10 keeps the header clear of the dialog's absolute close (X) on desktop */}
      <div className="flex items-center gap-2 border-b p-2 pr-10">
        <Button
          ref={backRef}
          type="button"
          variant="ghost"
          size="sm"
          className="gap-1"
          onClick={onBack}
        >
          <ArrowLeftIcon className="size-4" />
          Zurück
        </Button>
        <span
          title={media.title}
          className="min-w-0 grow truncate text-sm font-medium"
        >
          {media.title}
        </span>
        <Button
          asChild
          type="button"
          variant="ghost"
          size="sm"
          className="gap-1"
        >
          <a href={externalHref} target="_blank" rel="noopener noreferrer">
            <ExternalLinkIcon className="size-4" />
            <span className="hidden sm:inline">Neuer Tab</span>
          </a>
        </Button>
      </div>
      {/* Definite height (not just min-height): a percentage-height <iframe>
          collapses without a resolved parent height, which rendered the PDF as a
          thin broken strip. A <video> survives via its intrinsic size; the iframe
          needs this. */}
      <div className="relative flex h-[72vh] items-center justify-center bg-muted">
        {failed ? (
          <div className="flex flex-col items-center gap-3 p-6 text-center">
            <p className="text-sm text-foreground">
              Dieser Beleg konnte hier nicht geladen werden.
            </p>
            <Button asChild type="button" variant="default" size="sm">
              <a href={externalHref} target="_blank" rel="noopener noreferrer">
                <ExternalLinkIcon className="mr-1 size-4" />
                In neuem Tab öffnen
              </a>
            </Button>
          </div>
        ) : (
          <>
            {/* Loading affordance until the media paints — a speech video or a
                proxied PDF can take a few seconds, and a silent blank box reads
                as "frozen/broken". Overlaid so it disappears on load/error. */}
            {!loaded && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted-foreground">
                <Loader2Icon className="size-6 animate-spin" />
                <span className="text-sm">Beleg wird geladen …</span>
              </div>
            )}
            {media.kind === 'video' ? (
              <video
                src={media.url}
                controls
                playsInline
                aria-label={media.title}
                className="size-full bg-black"
                onLoadedMetadata={(event) => {
                  // Seek reliably to the cited moment regardless of #t= support.
                  if (seekSeconds !== null) {
                    event.currentTarget.currentTime = seekSeconds;
                  }
                }}
                onLoadedData={() => setLoaded(true)}
                onError={() => setFailed(true)}
              />
            ) : (
              <iframe
                src={pdfViewerSrc(media.url, media.page, media.search)}
                title={media.title}
                className="size-full border-0"
                onLoad={() => setLoaded(true)}
                onError={() => setFailed(true)}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * A single source row in the "Quellen" list. Opens its format(s) in the in-page
 * viewer via `onOpenMedia`. A merged speech (both a video and a PDF transcript)
 * renders TWO quick-links for the same source; every other source is a single
 * clickable row whose whole surface (including the format badge) opens it.
 */
export function SourceRow({
  source,
  displayNumber,
  badgeClassName,
  onOpenMedia,
}: {
  source: Source;
  displayNumber: number;
  badgeClassName?: string;
  onOpenMedia: (media: ActiveMedia) => void;
}) {
  const links = getSourceMediaLinks(source);

  const open = (link: SourceMediaLink) => {
    const resolved = resolveMediaOpen(link, source);
    if ('viewer' in resolved) {
      onOpenMedia(resolved.viewer);
    } else {
      openExternally(resolved.newTab);
    }
  };

  const openPrimary = () => openSourceMedia(source, onOpenMedia);

  const numberBadge = (
    <div
      className={cn(
        'inline-flex h-5 min-w-5 shrink-0 items-center justify-center rounded-full bg-muted px-1 text-xs tabular-nums',
        badgeClassName,
      )}
    >
      {displayNumber}
    </div>
  );

  const titleBlock = (
    <div className="flex min-w-0 grow flex-col justify-start overflow-hidden">
      <div className="flex grow flex-row items-center gap-2">
        {numberBadge}
        <p className="grow truncate text-start" title={source.source}>
          {source.source}
        </p>
      </div>
      {source.document_publish_date && (
        <span className="text-left text-xs text-muted-foreground">
          Veröffentlicht am:{' '}
          <span className="font-bold">
            {formatGermanDate(source.document_publish_date)}
          </span>
        </span>
      )}
    </div>
  );

  // Merged speech (video + PDF) → two quick-links for the SAME source. The row is
  // a div because it holds multiple buttons; the title opens the primary (video).
  if (links.length >= 2) {
    return (
      <div className="flex flex-row items-center justify-between gap-2 rounded-md p-2 transition-colors hover:bg-muted/50">
        <button
          type="button"
          onClick={openPrimary}
          title={source.source}
          className="flex min-w-0 grow flex-col justify-start overflow-hidden text-start"
        >
          {titleBlock}
        </button>
        <div className="flex shrink-0 items-center gap-1.5">
          {links.map((link) => (
            <Button
              key={link.kind}
              type="button"
              variant="secondary"
              size="sm"
              className="h-8 gap-1 px-2 text-xs"
              onClick={() => open(link)}
              aria-label={
                link.kind === 'video'
                  ? `Video ansehen${
                      videoTimestampSeconds(link.url) !== null
                        ? ` ab ${link.label.replace('▶ ', '')}`
                        : ''
                    }`
                  : 'PDF-Transkript ansehen'
              }
            >
              {link.kind === 'video' ? (
                <PlayIcon className="size-3.5" />
              ) : (
                <FileTextIcon className="size-3.5" />
              )}
              {link.kind === 'video' ? link.label.replace('▶ ', '') : 'PDF'}
            </Button>
          ))}
          {source.party_id && <ChatMessageIcon partyId={source.party_id} />}
        </div>
      </div>
    );
  }

  // Single (or no) media link → the whole row is one button, so clicking anywhere
  // (including the format badge) opens it.
  return (
    <button
      type="button"
      onClick={openPrimary}
      title={source.source}
      className="flex flex-row items-center justify-between gap-2 rounded-md p-2 text-start transition-colors hover:bg-muted/50 active:bg-muted"
    >
      {titleBlock}
      <div className="flex shrink-0 items-center gap-1.5">
        <span className="flex h-8 items-center justify-center whitespace-nowrap rounded-md bg-muted px-2 text-xs font-medium text-foreground">
          {sourceBadgeLabel(source)}
        </span>
        {source.party_id && <ChatMessageIcon partyId={source.party_id} />}
      </div>
    </button>
  );
}
