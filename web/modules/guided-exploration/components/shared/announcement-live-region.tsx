'use client';

import {
  selectAnnouncement,
  selectAnnouncementId,
  useExplorationStore,
} from '@/modules/guided-exploration/store';

/**
 * Renders the store's current screen-reader announcement into a single
 * visually-hidden polite live region. Mount once per exploration surface.
 * Keying on `announcementId` makes identical back-to-back messages re-announce.
 */
export function AnnouncementLiveRegion() {
  const announcement = useExplorationStore(selectAnnouncement);
  const announcementId = useExplorationStore(selectAnnouncementId);

  return (
    <div
      key={announcementId}
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"
    >
      {announcement}
    </div>
  );
}
