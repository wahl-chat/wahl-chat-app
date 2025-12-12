import { SCROLL_CONTAINER_ID } from '@/lib/scroll-constants';
import { chatViewScrollToBottom } from '@/lib/scroll-utils';
import { useEffect } from 'react';

type Props = {
  children: React.ReactNode;
};

function ChatMessagesScrollView({ children }: Props) {
  useEffect(() => {
    chatViewScrollToBottom({ behavior: 'instant' });
  }, []);

  return (
    <div
      className="grow overflow-x-hidden overflow-y-scroll"
      id={SCROLL_CONTAINER_ID}
    >
      {children}
    </div>
  );
}

export default ChatMessagesScrollView;
