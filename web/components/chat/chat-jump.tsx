'use client';
import { ArrowUpIcon } from 'lucide-react';
import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

type ChatJump = {
  /** The element a jump left from; the pill scrolls back to it. */
  origin: string | null;
  jump: (origin: string, target: string) => void;
  back: () => void;
  clear: () => void;
};

const ChatJumpContext = createContext<ChatJump | null>(null);

/** Scrolls to the element and moves focus there; false when it is gone. */
function scrollTo(id: string): boolean {
  const element = document.getElementById(id);
  if (!element) return false;
  element.scrollIntoView({ behavior: 'smooth', block: 'start' });
  element.focus({ preventScroll: true });
  return true;
}

export function ChatJumpProvider({ children }: { children: ReactNode }) {
  const [origin, setOrigin] = useState<string | null>(null);
  const jump = useCallback((from: string, target: string) => {
    if (scrollTo(target)) setOrigin(from);
  }, []);
  const back = useCallback(() => {
    if (origin) scrollTo(origin);
    setOrigin(null);
  }, [origin]);
  const clear = useCallback(() => setOrigin(null), []);
  const value = useMemo(
    () => ({ origin, jump, back, clear }),
    [origin, jump, back, clear],
  );
  return (
    <ChatJumpContext.Provider value={value}>
      {children}
    </ChatJumpContext.Provider>
  );
}

export function useChatJump(): ChatJump | null {
  return useContext(ChatJumpContext);
}

/** Floats above the input after a jump; gone once the origin is back in
 * view, whether by the pill or by scrolling. */
export function ChatJumpBackPill() {
  const jumpState = useChatJump();
  const origin = jumpState?.origin ?? null;
  const clear = jumpState?.clear;
  const [left, setLeft] = useState(false);

  useEffect(() => {
    setLeft(false);
    const element = origin ? document.getElementById(origin) : null;
    if (!element) return;
    let away = false;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) {
        away = true;
        setLeft(true);
      } else if (away) {
        away = false;
        setLeft(false);
        clear?.();
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [origin, clear]);

  if (!origin || !left) return null;
  return (
    <div className="pointer-events-none absolute inset-x-0 -top-14 z-10 flex justify-center">
      <button
        type="button"
        onClick={jumpState?.back}
        className="pointer-events-auto mx-auto flex min-h-10 items-center gap-1.5 rounded-full bg-foreground px-4 text-sm font-semibold text-background shadow-lg"
      >
        <ArrowUpIcon className="size-4" aria-hidden />
        Zurück zu Kurz gesagt
      </button>
    </div>
  );
}
