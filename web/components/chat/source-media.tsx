'use client';

import { ChatMessageIcon } from '@/components/chat/chat-message-icon';
import { Button } from '@/components/ui/button';
import type { Source } from '@/lib/stores/chat-store.types';
import {
  type SourceMediaLink,
  cn,
  formatGermanDate,
  getSourceMediaLinks,
  isPdfUrl,
  pdfViewerFileUrl,
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
import dynamic from 'next/dynamic';
import { useEffect, useRef, useState } from 'react';

// pdf.js + worker only load when a PDF is actually opened.
const PdfViewer = dynamic(() => import('@/components/chat/pdf-viewer'), {
  ssr: false,
});

export type ActiveMedia = {
  kind: 'video' | 'pdf';
  url: string;
  title: string;
  /** 1-based PDF page to open at (e.g. an AW Wahlprogramm page citation). */
  page?: number;
  /** Cited text to highlight in the PDF viewer (best effort). */
  snippet?: string;
};

function openExternally(url: string): void {
  window.open(url, '_blank', 'noopener,noreferrer');
}

/**
 * PDF open-parameter fragment for native browser viewers: `#page=N` (exact, only
 * when N > 1). Degrades gracefully — an unsupported viewer just ignores it.
 */
function pdfFragment(page?: number): string {
  return page && page > 1 ? `#page=${page}` : '';
}

/**
 * Append the PDF open-parameter fragment to a PDF URL — unless the URL already
 * carries its own `#` fragment (never clobber an existing anchor). Callers gate
 * on the target actually being a PDF; non-PDF links must not get PDF params.
 */
function withPdfFragment(url: string, page?: number): string {
  if (url.includes('#')) {
    return url;
  }
  return `${url}${pdfFragment(page)}`;
}

/**
 * Decide how a source's format link opens: the in-page viewer (videos always;
 * PDFs the pdf.js viewer can fetch — our GCS buckets directly, allowlisted
 * institution hosts via the proxy) or a new tab (everything else). The viewer
 * renders with pdf.js on every device, so cited-page jumps and highlighting
 * work on mobile too — native viewers ignore `#page=N` there.
 */
function resolveMediaOpen(
  link: SourceMediaLink,
  source: Source,
): { viewer: ActiveMedia } | { newTab: string } {
  const title = source.source;
  if (link.kind === 'video') {
    return { viewer: { kind: 'video', url: link.url, title } };
  }
  if (pdfViewerFileUrl(link.url) !== null) {
    return {
      viewer: {
        kind: 'pdf',
        url: link.url,
        title,
        page: source.page,
        snippet: source.snippet,
      },
    };
  }
  // New tab (unfetchable host): keep the page anchor on the raw URL.
  // `link.kind` is 'pdf' here (video returned above), and withPdfFragment
  // skips URLs that already carry a fragment.
  return { newTab: withPdfFragment(link.url, source.page) };
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
    // Plain weblink (no embeddable media) — open externally. PDF open-params
    // only make sense on PDF targets; plain weblinks open unmodified.
    openExternally(
      isPdfUrl(source.url)
        ? withPdfFragment(source.url, source.page)
        : source.url,
    );
  }
}

/**
 * The in-page media view that replaces the sources list inside the "Quellen"
 * dialog: a native <video> for speech deep-links (seeks to the cited moment via
 * `#t=`) or the pdf.js viewer for documents. A "Neuer Tab" escape hatch is
 * always available, and a load failure shows an explicit fallback instead of a
 * silent blank box.
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
    media.kind === 'pdf' ? withPdfFragment(media.url, media.page) : media.url;

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
      {/* Definite height (not just min-height): the viewer sizes itself from
          its parent, which needs a resolved height to size against. */}
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
              <PdfViewer
                // Non-null: resolveMediaOpen only routes fetchable PDFs here.
                fileUrl={pdfViewerFileUrl(media.url) as string}
                initialPage={media.page}
                snippet={media.snippet}
                title={media.title}
                onReady={() => setLoaded(true)}
                onFail={() => setFailed(true)}
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
