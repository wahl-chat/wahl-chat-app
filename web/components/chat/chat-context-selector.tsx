'use client';

import ContextSwitcher from '@/components/context/context-switcher';

export function ChatContextSelector() {
  return (
    <ContextSwitcher buildHref={(contextId) => `/${contextId}`} area="chat" />
  );
}

export default ChatContextSelector;
