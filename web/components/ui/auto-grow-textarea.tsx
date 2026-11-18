'use client';

import { cn } from '@/lib/utils';
import { forwardRef, useCallback, useEffect, useRef, useState } from 'react';

const LINE_PX = 24;
const MAX_LINES = 5;
// Upward scroll elsewhere on the page that folds the box back to one line.
const COLLAPSE_SCROLL_PX = 24;

type Props = Omit<
  React.TextareaHTMLAttributes<HTMLTextAreaElement>,
  'rows' | 'onSubmit'
> & {
  value: string;
  /** Enter sends; Shift+Enter breaks the line. */
  onSubmit: () => void;
};

/** A message box that grows with its text up to five lines, then scrolls.
 * Scrolling the page back up folds it to one line; touching it unfolds it. */
const AutoGrowTextarea = forwardRef<HTMLTextAreaElement, Props>(
  function AutoGrowTextarea(
    { value, onSubmit, className, onFocus, onPointerDown, ...props },
    forwardedRef,
  ) {
    const ref = useRef<HTMLTextAreaElement | null>(null);
    const [collapsed, setCollapsed] = useState(false);

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

    useEffect(() => {
      const node = ref.current;
      if (!node) {
        return;
      }
      const padding =
        Number.parseFloat(getComputedStyle(node).paddingTop) +
        Number.parseFloat(getComputedStyle(node).paddingBottom);
      node.style.height = 'auto';
      const lines = collapsed ? 1 : MAX_LINES;
      node.style.height = `${Math.min(node.scrollHeight, lines * LINE_PX + padding)}px`;
      if (collapsed) {
        node.scrollTop = 0;
      }
    }, [value, collapsed]);

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
        enterKeyHint="send"
        className={cn('block resize-none leading-6', className)}
        onFocus={(event) => {
          setCollapsed(false);
          onFocus?.(event);
        }}
        onPointerDown={(event) => {
          setCollapsed(false);
          onPointerDown?.(event);
        }}
        onKeyDown={(event) => {
          if (
            event.key === 'Enter' &&
            !event.shiftKey &&
            !event.nativeEvent.isComposing
          ) {
            event.preventDefault();
            onSubmit();
          }
        }}
        {...props}
      />
    );
  },
);

export default AutoGrowTextarea;
