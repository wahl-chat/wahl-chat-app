'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import {
  type ActiveMedia,
  SourceMediaViewer,
  openSourceMedia,
} from '@/components/chat/source-media';
import type { Source } from '@/lib/stores/chat-store.types';
import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';

type MediaViewerContextValue = {
  /** Open a source's primary media in-page (or a new tab when not embeddable). */
  openSource: (source: Source) => void;
};

const MediaViewerContext = createContext<MediaViewerContextValue | null>(null);

/** Access the app-wide in-page media viewer (null when no provider is mounted). */
export function useMediaViewer(): MediaViewerContextValue | null {
  return useContext(MediaViewerContext);
}

/**
 * Mounts a single in-page media viewer dialog and exposes `openSource`, so BOTH
 * the "Quellen" list and the in-text citation pills open a source the same way —
 * video/PDF in-page, off-allowlist/touch/weblinks in a new tab — instead of the
 * citation pills always dumping the user into an external tab.
 */
export function MediaViewerProvider({ children }: { children: ReactNode }) {
  const [activeMedia, setActiveMedia] = useState<ActiveMedia | null>(null);

  const openSource = useCallback((source: Source) => {
    openSourceMedia(source, setActiveMedia);
  }, []);

  const value = useMemo(() => ({ openSource }), [openSource]);

  return (
    <MediaViewerContext.Provider value={value}>
      {children}
      <ResponsiveDialog
        open={activeMedia !== null}
        onOpenChange={(open) => {
          if (!open) setActiveMedia(null);
        }}
      >
        <ResponsiveDialogContent className="flex max-h-[95dvh] flex-col md:max-w-3xl">
          {activeMedia && (
            <>
              <ResponsiveDialogHeader className="sr-only">
                <ResponsiveDialogTitle>
                  {activeMedia.title}
                </ResponsiveDialogTitle>
                <ResponsiveDialogDescription>
                  Beleg im Fenster ansehen.
                </ResponsiveDialogDescription>
              </ResponsiveDialogHeader>
              <SourceMediaViewer
                media={activeMedia}
                onBack={() => setActiveMedia(null)}
              />
            </>
          )}
        </ResponsiveDialogContent>
      </ResponsiveDialog>
    </MediaViewerContext.Provider>
  );
}
