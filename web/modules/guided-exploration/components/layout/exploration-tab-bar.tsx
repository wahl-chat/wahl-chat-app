'use client';

import { cn } from '@/lib/utils';
import type { ExplorationTabState } from '@/modules/guided-exploration/store';
import { Loader2, MessageSquare, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

const TAB_DOT_COLORS = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-purple-500',
  'bg-rose-500',
  'bg-cyan-500',
];

const EXPLORATION_PANEL_ID = 'exploration-panel';

function tabDomId(tabId: string) {
  return `exploration-tab-${tabId}`;
}

interface ExplorationTabBarProps {
  activeTabId: 'chat' | string;
  explorationTabs: Record<string, ExplorationTabState>;
  isInExploration?: boolean;
  onTabSwitch: (tabId: 'chat' | string) => void;
  onTabClose?: (explorationId: string) => void;
}

export function ExplorationTabBar({
  activeTabId,
  explorationTabs,
  isInExploration = false,
  onTabSwitch,
  onTabClose,
}: ExplorationTabBarProps) {
  const tabs = Object.values(explorationTabs);
  const tabListRef = useRef<HTMLDivElement>(null);

  const orderedIds: Array<'chat' | string> = [
    'chat',
    ...tabs.map((t) => t.explorationId),
  ];

  const activeIndex = Math.max(0, orderedIds.indexOf(activeTabId));
  const [focusedIndex, setFocusedIndex] = useState(activeIndex);

  // Keep focused index in sync with the active tab so that after
  // navigation the right tab is tabbable again.
  useEffect(() => {
    setFocusedIndex(activeIndex);
  }, [activeIndex]);

  const focusTab = useCallback(
    (index: number) => {
      const targetId = orderedIds[index];
      if (!targetId) return;
      const el = tabListRef.current?.querySelector<HTMLButtonElement>(
        `#${CSS.escape(tabDomId(targetId))}`,
      );
      el?.focus();
    },
    [orderedIds],
  );

  const handleTabKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
      const count = orderedIds.length;
      if (count === 0) return;

      // Delete/Backspace closes the tab (ARIA APG closeable-tabs pattern).
      if (
        (e.key === 'Delete' || e.key === 'Backspace') &&
        onTabClose &&
        index > 0
      ) {
        e.preventDefault();
        const targetId = orderedIds[index];
        if (typeof targetId === 'string') onTabClose(targetId);
        return;
      }

      let nextIndex: number | null = null;
      switch (e.key) {
        case 'ArrowRight':
          nextIndex = (index + 1) % count;
          break;
        case 'ArrowLeft':
          nextIndex = (index - 1 + count) % count;
          break;
        case 'Home':
          nextIndex = 0;
          break;
        case 'End':
          nextIndex = count - 1;
          break;
        default:
          return;
      }

      e.preventDefault();
      setFocusedIndex(nextIndex);
      focusTab(nextIndex);
    },
    [orderedIds, focusTab, onTabClose],
  );

  if (tabs.length === 0 && !isInExploration) return null;

  return (
    <div
      ref={tabListRef}
      className="flex items-end gap-0 bg-muted/40 px-1 pt-1"
      role="tablist"
      aria-label="Chat und Erkundungen"
    >
      {/* Chat tab */}
      <Tab
        tabId="chat"
        isActive={activeTabId === 'chat'}
        tabIndex={focusedIndex === 0 ? 0 : -1}
        onActivate={() => onTabSwitch('chat')}
        onKeyDown={(e) => handleTabKeyDown(e, 0)}
        icon={<MessageSquare className="size-4" aria-hidden="true" />}
        label="Chat"
      />

      {/* Exploration tabs */}
      {tabs.map((tab, idx) => {
        const index = idx + 1;
        const isActive = activeTabId === tab.explorationId;
        const dotColor = TAB_DOT_COLORS[tab.colorIndex % TAB_DOT_COLORS.length];

        return (
          <Tab
            key={tab.explorationId}
            tabId={tab.explorationId}
            isActive={isActive}
            tabIndex={focusedIndex === index ? 0 : -1}
            onActivate={() => onTabSwitch(tab.explorationId)}
            onKeyDown={(e) => handleTabKeyDown(e, index)}
            icon={
              <span
                className={cn('inline-block size-2.5 rounded-full', dotColor)}
                aria-hidden="true"
              />
            }
            label={tab.label}
            hasUnread={tab.hasUnread && !isActive}
            onClose={
              onTabClose ? () => onTabClose(tab.explorationId) : undefined
            }
            closeLabel={`Erkundung "${tab.label}" schliessen`}
          />
        );
      })}

      {/* Spacer to extend the bottom border across remaining width */}
      <div className="min-w-0 flex-1 border-b" />
    </div>
  );
}

interface TabProps {
  tabId: string;
  isActive: boolean;
  tabIndex: number;
  onActivate: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLButtonElement>) => void;
  icon: React.ReactNode;
  label: string;
  hasUnread?: boolean;
  onClose?: () => void;
  closeLabel?: string;
}

function Tab({
  tabId,
  isActive,
  tabIndex,
  onActivate,
  onKeyDown,
  icon,
  label,
  hasUnread,
  onClose,
  closeLabel,
}: TabProps) {
  return (
    <button
      type="button"
      role="tab"
      id={tabDomId(tabId)}
      aria-selected={isActive}
      aria-controls={EXPLORATION_PANEL_ID}
      tabIndex={tabIndex}
      onClick={onActivate}
      onKeyDown={onKeyDown}
      className={cn(
        'group relative flex max-w-[240px] shrink-0 items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        isActive
          ? 'rounded-t-lg border border-b-0 border-border bg-background text-foreground'
          : '-mb-px border-b border-transparent text-muted-foreground hover:text-foreground',
      )}
    >
      <span className="shrink-0">{icon}</span>
      <span className="max-w-[160px] truncate">{label}</span>
      {hasUnread && (
        <Loader2
          className="size-3 shrink-0 animate-spin text-primary"
          aria-hidden="true"
        />
      )}
      {onClose && (
        <span
          role="button"
          tabIndex={-1}
          aria-label={closeLabel}
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          onKeyDown={(e) => {
            // Prevent nested activation when Enter/Space reaches the tab.
            if (e.key === 'Enter' || e.key === ' ') {
              e.stopPropagation();
              e.preventDefault();
              onClose();
            }
          }}
          className={cn(
            '-mr-1 ml-1 inline-flex items-center justify-center rounded p-0.5 transition-opacity duration-150',
            isActive
              ? 'text-muted-foreground hover:bg-muted hover:text-foreground'
              : 'opacity-0 group-hover:opacity-100 group-hover:text-muted-foreground group-hover:hover:text-foreground',
          )}
        >
          <X className="size-3" />
        </span>
      )}
    </button>
  );
}

export { EXPLORATION_PANEL_ID };
