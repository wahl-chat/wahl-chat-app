'use client';

import { cn } from '@/lib/utils';
import type { ExplorationTabState } from '@/modules/guided-exploration/store';
import { Loader2, MessageSquare, X } from 'lucide-react';

const TAB_DOT_COLORS = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-purple-500',
  'bg-rose-500',
  'bg-cyan-500',
];

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

  if (tabs.length === 0 && !isInExploration) return null;

  return (
    <div
      className="flex items-end gap-0 bg-muted/40 px-1 pt-1"
      role="tablist"
      aria-label="Chat und Erkundungen"
    >
      {/* Chat tab */}
      <Tab
        isActive={activeTabId === 'chat'}
        onClick={() => onTabSwitch('chat')}
        icon={<MessageSquare className="size-4" />}
        label="Chat"
      />

      {/* Exploration tabs */}
      {tabs.map((tab) => {
        const isActive = activeTabId === tab.explorationId;
        const dotColor = TAB_DOT_COLORS[tab.colorIndex % TAB_DOT_COLORS.length];

        return (
          <Tab
            key={tab.explorationId}
            isActive={isActive}
            onClick={() => onTabSwitch(tab.explorationId)}
            icon={
              <span
                className={cn('inline-block size-2.5 rounded-full', dotColor)}
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
  isActive: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  hasUnread?: boolean;
  onClose?: () => void;
  closeLabel?: string;
}

function Tab({
  isActive,
  onClick,
  icon,
  label,
  hasUnread,
  onClose,
  closeLabel,
}: TabProps) {
  return (
    <div
      role="tab"
      aria-selected={isActive}
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        'group relative flex max-w-[240px] shrink-0 cursor-pointer items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors duration-150',
        isActive
          ? 'rounded-t-lg border border-b-0 border-border bg-background text-foreground'
          : '-mb-px border-b border-transparent text-muted-foreground hover:text-foreground',
      )}
    >
      <span className="shrink-0">{icon}</span>
      <span className="max-w-[160px] truncate">{label}</span>
      {hasUnread && (
        <Loader2 className="size-3 shrink-0 animate-spin text-primary" />
      )}
      {onClose && (
        <span
          role="button"
          tabIndex={0}
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.stopPropagation();
              onClose();
            }
          }}
          className={cn(
            '-mr-1 rounded p-0.5 transition-opacity duration-150',
            isActive
              ? 'text-muted-foreground hover:bg-muted hover:text-foreground'
              : 'opacity-0 group-hover:opacity-100 group-hover:text-muted-foreground group-hover:hover:text-foreground',
          )}
          aria-label={closeLabel}
        >
          <X className="size-3" />
        </span>
      )}
    </div>
  );
}
