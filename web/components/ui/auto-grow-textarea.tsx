'use client';

import { cn } from '@/lib/utils';
import {
  forwardRef,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';

const LINE_PX = 24;
const MAX_LINES = 5;
// Upward scroll elsewhere on the page that folds the box back to one line.
const COLLAPSE_SCROLL_PX = 24;
// What an IME reports for a key that belongs to the word being composed.
const IME_KEY_CODE = 229;

type Props = Omit<
  React.TextareaHTMLAttributes<HTMLTextAreaElement>,
  'rows' | 'onSubmit'
> & {
  value: string;
  /** Enter sends; Shift+Enter breaks the line. On touch screens Return
   * always breaks the line and the send button sends. */
  onSubmit: () => void;
};

/** A message box that grows with its text up to five lines, then scrolls.
 * Scrolling the page back up folds it to one line; touching or typing
 * unfolds it. */
const AutoGrowTextarea = forwardRef<HTMLTextAreaElement, Props>(
  function AutoGrowTextarea(
    {
      value,
      onSubmit,
      className,
      onFocus,
      onBlur,
      onPointerDown,
      onKeyDown,
      onChange,
      onCompositionStart,
      onCompositionEnd,
      ...props
    },
    forwardedRef,
  ) {
    const ref = useRef<HTMLTextAreaElement | null>(null);
    const [collapsed, setCollapsed] = useState(false);
    const touch = useCoarsePointer();
    // Bumped when the box changes width, so the height follows the new wrap.
    const [width, setWidth] = useState(0);
    const composing = useRef(false);
    const [focused, setFocused] = useState(false);
    useKeyboardCover(focused ? ref : null);

    const setRefs = useCallback(
      (node: HTMLTextAreaElement | null) => {
        ref.current = node;
        if (typeof forwardedRef === 'function') {
          forwardedRef(node);
        } else if (forwardedRef) {
          forwardedRef.current = node;
        }
      },
      [forwardedRef],
    );

    useLayoutEffect(() => {
      const node = ref.current;
      if (!node) {
        return;
      }
      const style = getComputedStyle(node);
      const padding =
        Number.parseFloat(style.paddingTop) +
        Number.parseFloat(style.paddingBottom);
      node.style.height = 'auto';
      const lines = collapsed ? 1 : MAX_LINES;
      node.style.height = `${Math.min(node.scrollHeight, lines * LINE_PX + padding)}px`;
      if (collapsed) {
        node.scrollTop = 0;
      }
    }, [value, collapsed, width]);

    useEffect(() => {
      const node = ref.current;
      if (!node || typeof ResizeObserver === 'undefined') {
        return;
      }
      const observer = new ResizeObserver(([entry]) =>
        setWidth(Math.round(entry.contentRect.width)),
      );
      observer.observe(node);
      return () => observer.disconnect();
    }, []);

    useEffect(() => {
      const last = new WeakMap<EventTarget, number>();
      const onScroll = (event: Event) => {
        const target = event.target;
        if (!target || target === ref.current) {
          return;
        }
        const top =
          target === document
            ? window.scrollY
            : (target as HTMLElement).scrollTop;
        const before = last.get(target);
        last.set(target, top);
        if (before !== undefined && before - top > COLLAPSE_SCROLL_PX) {
          setCollapsed(true);
        }
      };
      document.addEventListener('scroll', onScroll, {
        capture: true,
        passive: true,
      });
      return () =>
        document.removeEventListener('scroll', onScroll, { capture: true });
    }, []);

    return (
      <textarea
        ref={setRefs}
        rows={1}
        value={value}
        enterKeyHint={touch ? 'enter' : 'send'}
        className={cn('block resize-none leading-6', className)}
        onFocus={(event) => {
          setCollapsed(false);
          setFocused(true);
          onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          onBlur?.(event);
        }}
        onPointerDown={(event) => {
          setCollapsed(false);
          onPointerDown?.(event);
        }}
        onChange={(event) => {
          setCollapsed(false);
          onChange?.(event);
        }}
        onCompositionStart={(event) => {
          composing.current = true;
          onCompositionStart?.(event);
        }}
        onCompositionEnd={(event) => {
          composing.current = false;
          onCompositionEnd?.(event);
        }}
        onKeyDown={(event) => {
          onKeyDown?.(event);
          if (
            touch ||
            event.defaultPrevented ||
            event.key !== 'Enter' ||
            event.shiftKey ||
            composing.current ||
            event.nativeEvent.isComposing ||
            event.nativeEvent.keyCode === IME_KEY_CODE
          ) {
            return;
          }
          event.preventDefault();
          onSubmit();
        }}
        {...props}
      />
    );
  },
);

export default AutoGrowTextarea;

/** Phones and tablets: the primary pointer is a finger. */
export function useCoarsePointer(): boolean {
  const [coarse, setCoarse] = useState(false);
  useEffect(() => {
    const query = window.matchMedia?.('(pointer: coarse)');
    if (!query) {
      return;
    }
    setCoarse(query.matches);
    const onChange = (event: MediaQueryListEvent) => setCoarse(event.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);
  return coarse;
}

/** The nearest painted background around the box, skipping its own form. */
function surroundingBackground(node: HTMLElement): string {
  let element = node.closest('form')?.parentElement ?? node.parentElement;
  while (element) {
    const color = getComputedStyle(element).backgroundColor;
    if (color && color !== 'transparent' && !color.endsWith(', 0)')) {
      return color;
    }
    element = element.parentElement;
  }
  return getComputedStyle(document.body).backgroundColor;
}

/** With a phone keyboard open, iOS Safari shows the page below the visible
 * part behind its toolbar, but without fixed and sticky boxes, so the feed
 * shows between the box and the keyboard. A plain box in the page covers
 * that strip in the box's surrounding colour; elsewhere it sits below the
 * screen. */
function useKeyboardCover(target: React.RefObject<HTMLElement | null> | null) {
  useEffect(() => {
    const node = target?.current;
    const viewport = window.visualViewport;
    if (!node || !viewport) {
      return;
    }
    const cover = document.createElement('div');
    cover.setAttribute('aria-hidden', 'true');
    Object.assign(cover.style, {
      position: 'absolute',
      left: '0',
      width: '100%',
      // Over the page, under its ask bars (z-30 and up), sheets and dialogs.
      zIndex: '25',
      pointerEvents: 'none',
      background: surroundingBackground(node),
    });
    // Never past the page's end, so it adds no scroll room.
    const pageEnd = document.documentElement.scrollHeight;
    const place = () => {
      // From the box's lower edge, so no page peeks out between the two.
      const box = (node.closest('form') ?? node).getBoundingClientRect();
      const top = Math.min(
        viewport.pageTop + viewport.height,
        viewport.pageTop + box.bottom,
      );
      cover.style.top = `${top}px`;
      cover.style.height = `${Math.max(0, Math.min(window.innerHeight, pageEnd - top))}px`;
    };
    place();
    document.body.appendChild(cover);
    viewport.addEventListener('resize', place);
    viewport.addEventListener('scroll', place);
    window.addEventListener('scroll', place, { passive: true });
    return () => {
      viewport.removeEventListener('resize', place);
      viewport.removeEventListener('scroll', place);
      window.removeEventListener('scroll', place);
      cover.remove();
    };
  }, [target]);
}
