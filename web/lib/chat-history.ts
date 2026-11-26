import { DEFAULT_CONTEXT_ID, GENERAL_CONTEXT_ID } from '@/lib/constants';
import type { ChatSession } from '@/lib/firebase/firebase.types';

/** Sessions written before contexts existed belong to the default election. */
export function sessionContextId(session: ChatSession): string {
  return session.context_id ?? DEFAULT_CONTEXT_ID;
}

export function sessionHref(session: ChatSession): string {
  return `/${sessionContextId(session)}/session/${session.id}`;
}

/** The user's latest general chat, else a fresh one. History is newest first. */
export function generalChatHref(history: ChatSession[]): string {
  const latest = history.find(
    (session) => sessionContextId(session) === GENERAL_CONTEXT_ID,
  );
  return latest ? sessionHref(latest) : '/chat';
}
