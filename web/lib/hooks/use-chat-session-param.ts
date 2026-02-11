import { useParams } from 'next/navigation';

export function useChatSessionParam(): string | undefined {
  const { chatSessionId } = useParams();

  if (!chatSessionId) return undefined;

  if (typeof chatSessionId !== 'string')
    throw new Error('Chat Session ID is not a string');

  return chatSessionId;
}
