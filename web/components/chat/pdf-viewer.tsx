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
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { Document, Page, pdfjs } from 'react-pdf';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const ZOOM_STEPS = [0.6, 0.8, 1, 1.25, 1.5, 2, 3];
const PAGE_GAP = 8;
// Pages rendered around the visible one; the rest are placeholders so an
// 85-page manifesto stays cheap, especially on phones.
const RENDER_WINDOW = 2;
// A4 portrait, used until the real page size is known.
const FALLBACK_ASPECT = Math.SQRT2;

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
  /** 1-based page the citation points at. */
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
 * viewer, so cited-page jumps and text highlighting behave identically across
 * browsers and devices — mobile browsers ignore `#page=N` open parameters and
 * iOS renders PDF iframes unreliably, which is exactly what this replaces.
 *
 * Continuously scrollable like a native viewer: all pages are stacked, but only
 * those near the viewport actually render (placeholders elsewhere). The view
 * opens centered on the cited passage's highlight when the snippet matches,
 * else at the top of the cited page.
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
  const [currentPage, setCurrentPage] = useState(
    initialPage && initialPage > 0 ? initialPage : 1,
  );
  const [zoomIndex, setZoomIndex] = useState(2); // 1 = fit width
  const [containerWidth, setContainerWidth] = useState<number | null>(null);
  const [pageAspect, setPageAspect] = useState<number | null>(null);
  const [highlightItems, setHighlightItems] = useState<Set<number>>(
    () => new Set(),
  );
  // The page the citation targets — highlight matching only happens there.
  const rawCitedPage = initialPage && initialPage > 0 ? initialPage : 1;
  const citedPage = numPages ? Math.min(rawCitedPage, numPages) : rawCitedPage;
  // Until the cited page has painted, it is the ONLY page mounted: five large
  // canvases rendering at once starve the visible one and the viewer opens as
  // a white void for seconds. Neighbors mount after the first paint.
  const [citedPagePainted, setCitedPagePainted] = useState(false);
  // Center the highlight exactly once; afterwards the user owns the scroll.
  const autoScrolledToMark = useRef(false);

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

  const zoom = ZOOM_STEPS[zoomIndex];
  const pageWidth = containerWidth ? containerWidth * zoom : null;
  const pageHeight = pageWidth
    ? pageWidth * (pageAspect ?? FALLBACK_ASPECT)
    : null;
  const slotHeight = pageHeight ? pageHeight + PAGE_GAP : null;

  const scrollToPage = useCallback(
    (page: number) => {
      if (scrollRef.current && slotHeight) {
        scrollRef.current.scrollTop = (page - 1) * slotHeight;
      }
    },
    [slotHeight],
  );

  const onDocumentLoad = useCallback(
    (pdf: { numPages: number; getPage: (n: number) => Promise<unknown> }) => {
      setNumPages(pdf.numPages);
      const target = Math.min(citedPage, pdf.numPages);
      setCurrentPage(target);
      // Real page geometry for placeholder sizing and the initial jump.
      pdf
        .getPage(target)
        .then((page) => {
          const viewport = (
            page as {
              getViewport: (o: { scale: number }) => {
                width: number;
                height: number;
              };
            }
          ).getViewport({ scale: 1 });
          setPageAspect(viewport.height / viewport.width);
        })
        .catch(() => {
          // Placeholder fallback aspect is fine; highlight scroll still refines.
        });
    },
    [citedPage],
  );

  // The parent overlay drops when the cited page has actually PAINTED — after
  // document load the canvas still needs seconds on big manifestos, and hiding
  // the spinner then would show a white void.
  const onCitedPageRendered = useCallback(() => {
    setCitedPagePainted(true);
    onReady();
  }, [onReady]);

  // Jump to the cited page as soon as slot geometry exists, and re-anchor when
  // the aspect refines from fallback to real — both happen before first paint
  // settles. Never re-run afterwards (zoom handles its own anchoring).
  const initialJumpDone = useRef(false);
  const lastJumpAspect = useRef<number | null>(null);
  useEffect(() => {
    if (!numPages || !slotHeight) {
      return;
    }
    if (!initialJumpDone.current || lastJumpAspect.current !== pageAspect) {
      initialJumpDone.current = true;
      lastJumpAspect.current = pageAspect;
      if (!autoScrolledToMark.current) {
        scrollToPage(Math.min(citedPage, numPages));
      }
    }
  }, [numPages, slotHeight, pageAspect, citedPage, scrollToPage]);

  // Scroll-derived page indicator: the page under the viewport's midline.
  const onScroll = useCallback(() => {
    const scroller = scrollRef.current;
    if (!scroller || !slotHeight || !numPages) {
      return;
    }
    const midline = scroller.scrollTop + scroller.clientHeight / 2;
    const page = Math.min(
      numPages,
      Math.max(1, Math.floor(midline / slotHeight) + 1),
    );
    setCurrentPage(page);
  }, [slotHeight, numPages]);

  // TextItem vs TextMarkedContent: only real text items carry `str`; marked-
  // content entries still occupy indices, so keep positions aligned with ''.
  // transform[5] is the item's y in PDF text space — the matcher uses it to
  // keep visually distant matches (running footers) out of the passage cluster.
  const onTextSuccess = useCallback(
    (textContent: { items: unknown[] }) => {
      if (!snippet) {
        return;
      }
      const highlightInput = textContent.items.map((item) => {
        if (typeof item !== 'object' || item === null || !('str' in item)) {
          return { str: '', y: null };
        }
        const textItem = item as { str: unknown; transform?: unknown };
        const y = Array.isArray(textItem.transform)
          ? Number(textItem.transform[5])
          : null;
        return {
          str: String(textItem.str),
          y: Number.isFinite(y) ? y : null,
        };
      });
      setHighlightItems(matchSnippetItems(highlightInput, snippet));
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

  // Center the highlight once the cited page's text layer carries the marks.
  // Runs after every text-layer render of that page, but only acts once.
  const onCitedTextLayerRendered = useCallback(() => {
    if (autoScrolledToMark.current) {
      return;
    }
    const scroller = scrollRef.current;
    const marks = scroller?.querySelectorAll('mark');
    if (!scroller || !marks || marks.length === 0) {
      return;
    }
    autoScrolledToMark.current = true;
    // Visually topmost mark, NOT the first in the DOM: pdf.js text layers
    // follow the PDF content stream, which can put a footer before the body.
    let markTop = Number.POSITIVE_INFINITY;
    for (const mark of marks) {
      markTop = Math.min(markTop, mark.getBoundingClientRect().top);
    }
    const scrollerTop = scroller.getBoundingClientRect().top;
    scroller.scrollTop += markTop - scrollerTop - scroller.clientHeight * 0.3;
  }, []);

  // Keep the reading position anchored across a zoom change. The scroll
  // correction must land AFTER React commits the new page sizes — an rAF can
  // fire before the re-render and then scale against the old layout.
  const pendingZoomRatio = useRef<number | null>(null);
  const changeZoom = (nextIndex: number) => {
    pendingZoomRatio.current = ZOOM_STEPS[nextIndex] / ZOOM_STEPS[zoomIndex];
    setZoomIndex(nextIndex);
  };
  useLayoutEffect(() => {
    const scroller = scrollRef.current;
    const ratio = pendingZoomRatio.current;
    if (scroller && ratio !== null) {
      pendingZoomRatio.current = null;
      scroller.scrollTop *= ratio;
    }
  }, [zoomIndex]);

  const pageNumbers = numPages
    ? Array.from({ length: numPages }, (_, i) => i + 1)
    : [];

  return (
    <div ref={containerRef} className="flex size-full min-h-0 flex-col">
      <div className="flex items-center justify-center gap-1 border-b bg-background p-1.5">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2"
          disabled={currentPage <= 1}
          onClick={() => scrollToPage(currentPage - 1)}
          aria-label="Vorherige Seite"
        >
          <ChevronLeftIcon className="size-4" />
        </Button>
        <span className="min-w-20 text-center text-xs tabular-nums text-muted-foreground">
          Seite {currentPage}
          {numPages ? ` / ${numPages}` : ''}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 px-2"
          disabled={numPages !== null && currentPage >= numPages}
          onClick={() => scrollToPage(currentPage + 1)}
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
          onClick={() => changeZoom(zoomIndex - 1)}
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
          onClick={() => changeZoom(zoomIndex + 1)}
          aria-label="Vergrößern"
        >
          <ZoomInIcon className="size-4" />
        </Button>
      </div>
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="min-h-0 grow overflow-auto"
      >
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
          {pageNumbers.map((page) => {
            const isCitedPage = page === citedPage;
            const isNearViewport = citedPagePainted
              ? Math.abs(page - currentPage) <= RENDER_WINDOW
              : isCitedPage;
            return (
              // mx-auto centers a zoomed-out page; wider than the viewport it
              // degrades to left-anchored horizontal scrolling.
              <div
                key={page}
                className="mx-auto"
                style={{
                  width: pageWidth ?? undefined,
                  height: pageHeight ?? undefined,
                  marginBottom: PAGE_GAP,
                }}
              >
                {isNearViewport && pageWidth ? (
                  <Page
                    pageNumber={page}
                    width={pageWidth}
                    customTextRenderer={isCitedPage ? textRenderer : undefined}
                    onGetTextSuccess={isCitedPage ? onTextSuccess : undefined}
                    onRenderTextLayerSuccess={
                      isCitedPage ? onCitedTextLayerRendered : undefined
                    }
                    onRenderSuccess={
                      isCitedPage ? onCitedPageRendered : undefined
                    }
                    onRenderError={isCitedPage ? onFail : undefined}
                    renderAnnotationLayer={false}
                    loading={
                      <div
                        className="flex items-center justify-center text-muted-foreground"
                        style={{ height: pageHeight ?? 160 }}
                      >
                        <Loader2Icon className="size-6 animate-spin" />
                      </div>
                    }
                    aria-label={`${title} – Seite ${page}`}
                  />
                ) : (
                  <div className="size-full bg-background/50" />
                )}
              </div>
            );
          })}
        </Document>
      </div>
    </div>
  );
}

export default PdfViewer;
