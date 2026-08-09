'use client';

import { Button } from '@/components/ui/button';
import { escapeHtml, matchSnippetItems } from '@/lib/pdf-highlight';
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  Loader2Icon,
  ZoomInIcon,
  ZoomOutIcon,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const ZOOM_STEPS = [0.6, 0.8, 1, 1.25, 1.5, 2, 3];

/**
 * Highlight style is inlined (not a class) because customTextRenderer output is
 * raw HTML outside Tailwind's reach. `color: transparent` is load-bearing: the
 * text layer's glyphs must stay invisible so only the canvas text shows through.
 */
const MARK_HTML_OPEN =
  '<mark style="background:rgba(250,204,21,.45);color:transparent;border-radius:2px;padding:0">';

type PdfViewerProps = {
  /** Resolved fetchable URL (direct GCS or same-origin proxy). */
  fileUrl: string;
  /** 1-based page to open at. */
  initialPage?: number;
  /** Cited text to highlight (best effort — no match, no highlight). */
  snippet?: string;
  title: string;
  /** First successful document load — parent can drop its loading overlay. */
  onReady: () => void;
  /** Unrecoverable load failure — parent shows its new-tab fallback. */
  onFail: () => void;
};

/**
 * In-page PDF viewer rendered with pdf.js instead of the browser's native
 * viewer, so cited-page jumps (and text highlighting) behave identically across
 * browsers and devices — mobile browsers ignore `#page=N` open parameters and
 * iOS renders PDF iframes unreliably, which is exactly what this replaces.
 * Single-page view with page/zoom controls; the cited snippet is re-matched on
 * whatever page is shown, so it also survives manual navigation.
 */
function PdfViewer({
  fileUrl,
  initialPage,
  snippet,
  title,
  onReady,
  onFail,
}: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(
    initialPage && initialPage > 0 ? initialPage : 1,
  );
  const [zoomIndex, setZoomIndex] = useState(2); // 1 = fit width
  const [containerWidth, setContainerWidth] = useState<number | null>(null);
  const [highlightItems, setHighlightItems] = useState<Set<number>>(
    () => new Set(),
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) {
        setContainerWidth(width);
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const onDocumentLoad = useCallback(
    ({ numPages: total }: { numPages: number }) => {
      setNumPages(total);
      setPageNumber((current) => Math.min(current, total));
      onReady();
    },
    [onReady],
  );

  // TextItem vs TextMarkedContent: only real text items carry `str`; marked-
  // content entries still occupy indices, so keep positions aligned with ''.
  const onTextSuccess = useCallback(
    (textContent: { items: unknown[] }) => {
      if (!snippet) {
        return;
      }
      const strings = textContent.items.map((item) =>
        typeof item === 'object' && item !== null && 'str' in item
          ? String((item as { str: unknown }).str)
          : '',
      );
      setHighlightItems(matchSnippetItems(strings, snippet));
    },
    [snippet],
  );

  const textRenderer = useCallback(
    ({ str, itemIndex }: { str: string; itemIndex: number }) =>
      highlightItems.has(itemIndex)
        ? `${MARK_HTML_OPEN}${escapeHtml(str)}</mark>`
        : escapeHtml(str),
    [highlightItems],
  );

  // Bring the highlight into view once the text layer of the cited page is up.
  const onTextLayerRendered = useCallback(() => {
    const scroller = scrollRef.current;
    const mark = scroller?.querySelector('mark');
    if (scroller && mark) {
      const markTop = mark.getBoundingClientRect().top;
      const scrollerTop = scroller.getBoundingClientRect().top;
      scroller.scrollTop +=
        markTop - scrollerTop - scroller.clientHeight * 0.35;
    }
  }, []);

  const goTo = (page: number) => {
    setHighlightItems(new Set());
    setPageNumber(page);
  };

  const zoom = ZOOM_STEPS[zoomIndex];
  const pageWidth = containerWidth ? containerWidth * zoom : undefined;

  return (
    <div ref={containerRef} className="flex size-full min-h-0 flex-col">
      <div className="flex items-center justify-center gap-1 border-b bg-background p-1.5">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2"
          disabled={pageNumber <= 1}
          onClick={() => goTo(pageNumber - 1)}
          aria-label="Vorherige Seite"
        >
          <ChevronLeftIcon className="size-4" />
        </Button>
        <span className="min-w-20 text-center text-xs tabular-nums text-muted-foreground">
          Seite {pageNumber}
          {numPages ? ` / ${numPages}` : ''}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2"
          disabled={numPages !== null && pageNumber >= numPages}
          onClick={() => goTo(pageNumber + 1)}
          aria-label="Nächste Seite"
        >
          <ChevronRightIcon className="size-4" />
        </Button>
        <div className="mx-1 h-4 w-px bg-border" />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2"
          disabled={zoomIndex <= 0}
          onClick={() => setZoomIndex(zoomIndex - 1)}
          aria-label="Verkleinern"
        >
          <ZoomOutIcon className="size-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2"
          disabled={zoomIndex >= ZOOM_STEPS.length - 1}
          onClick={() => setZoomIndex(zoomIndex + 1)}
          aria-label="Vergrößern"
        >
          <ZoomInIcon className="size-4" />
        </Button>
      </div>
      <div ref={scrollRef} className="min-h-0 grow overflow-auto">
        <Document
          file={fileUrl}
          onLoadSuccess={onDocumentLoad}
          onLoadError={onFail}
          // The parent's loading overlay covers document fetch; a second
          // spinner here would stack under it.
          loading={null}
          error={null}
          externalLinkTarget="_blank"
        >
          <Page
            pageNumber={pageNumber}
            width={pageWidth}
            customTextRenderer={textRenderer}
            onGetTextSuccess={onTextSuccess}
            onRenderTextLayerSuccess={onTextLayerRendered}
            renderAnnotationLayer={false}
            loading={
              <div className="flex h-40 items-center justify-center text-muted-foreground">
                <Loader2Icon className="size-6 animate-spin" />
              </div>
            }
            aria-label={title}
          />
        </Document>
      </div>
    </div>
  );
}

export default PdfViewer;
