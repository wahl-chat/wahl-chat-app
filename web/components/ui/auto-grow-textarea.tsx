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
          onFocus?.(event);
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
function useCoarsePointer(): boolean {
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
