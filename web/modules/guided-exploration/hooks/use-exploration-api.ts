/**
 * useExplorationApi Hook
 * Provides typed API methods with store integration. Every method that
 * targets a specific exploration takes `explorationId` as a parameter — the
 * store no longer keeps a single "current" exploration pointer in v3.
 */

'use client';

import { useParams } from 'next/navigation';
import { useCallback } from 'react';

import { explorationApi } from '@/modules/guided-exploration/services/exploration-api';
import {
  connectionActions,
  conversationActions,
  explorationActions,
  selectSessionId,
  sessionActions,
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';

export interface UseExplorationApiReturn {
  /** Create a new session and connect */
  createSession: () => Promise<string>;

  /** Load an existing session */
  resumeSession: (sessionId: string) => Promise<void>;

  /** Load a specific exploration */
  loadExploration: (
    explorationId: string,
    options?: { signal?: AbortSignal },
  ) => Promise<void>;

  /**
   * Send a message or question. When `leafId` is set, `explorationId` is
   * required (the message scopes to that leaf inside that exploration).
   */
  sendMessage: (
    content: string,
    leafId?: string,
    explorationId?: string,
  ) => Promise<void>;

  /** Submit choice (summary or explore) */
  submitChoice: (
    queryId: string,
    choice: 'summary' | 'explore',
  ) => Promise<void>;

  /** Submit topic direction choices (multi-select) */
  submitDirectionChoice: (
    queryId: string,
    directions: Array<{ id: string; name: string }>,
  ) => Promise<void>;

  /** Request analysis for a specific leaf */
  requestAnalysis: (explorationId: string, leafId: string) => Promise<void>;

  /** End a specific exploration */
  endExploration: (explorationId: string) => Promise<void>;

  /** Mark a leaf as explored within an exploration */
  markExplored: (explorationId: string, leafId: string) => Promise<void>;

  /** Current session ID */
  sessionId: string | null;
}

/**
 * Hook providing API methods integrated with the store
 */
export function useExplorationApi(): UseExplorationApiReturn {
  const params = useParams();
  const contextId = params.contextId as string;
  const dispatch = useExplorationStore((s) => s.dispatch);
  const sessionId = useExplorationStore(selectSessionId);

  const createSession = useCallback(async (): Promise<string> => {
    dispatch(connectionActions.connecting());

    try {
      const response = await explorationApi.createSession({
        contextId,
      });

      dispatch(sessionActions.created(response.sessionId));

      return response.sessionId;
    } catch (error) {
      dispatch(
        connectionActions.disconnected(
          error instanceof Error ? error.message : 'Failed to create session',
        ),
      );
      throw error;
    }
  }, [dispatch, contextId]);

  const resumeSession = useCallback(
    async (existingSessionId: string): Promise<void> => {
      dispatch(connectionActions.connecting());

      try {
        const response = await explorationApi.getSession(existingSessionId);

        dispatch(sessionActions.loaded(response.sessionId));
        // Load session messages into the store
        if (response.messages && response.messages.length > 0) {
          dispatch(sessionActions.messagesLoaded(response.messages));
        }

        // Restore the exploration tree + status so reloads show the
        // correct per-leaf status and completed banner without waiting
        // for a separate loadExploration call.
        const activeExp = response.activeExploration;
        if (activeExp) {
          dispatch(
            explorationActions.started(
              activeExp.id,
              activeExp.tree,
              activeExp.status,
              activeExp.overview ?? null,
            ),
          );
        }
      } catch (error) {
        dispatch(
          connectionActions.disconnected(
            error instanceof Error ? error.message : 'Failed to resume session',
          ),
        );
        throw error;
      }
    },
    [dispatch],
  );

  const loadExploration = useCallback(
    async (
      expId: string,
      options?: { signal?: AbortSignal },
    ): Promise<void> => {
      if (!sessionId) {
        throw new Error('No active session');
      }

      const signal = options?.signal;
      if (signal?.aborted) return;

      // Loading an exploration is initiated from the chat tab.
      dispatch(uiActions.lastActionTabSet('chat'));
      dispatch(
        uiActions.thinkingStarted('retrieving', 'Erkundung wird geladen...'),
      );

      // Retry logic for timing issues (exploration may not be ready immediately)
      const maxRetries = 5;
      const baseDelay = 500;
      let lastError: Error | null = null;

      for (let attempt = 0; attempt < maxRetries; attempt++) {
        if (signal?.aborted) return;
        try {
          const response = await explorationApi.getExploration(
            sessionId,
            expId,
          );

          if (signal?.aborted) return;

          dispatch(
            explorationActions.started(
              response.id,
              response.tree,
              response.status,
            ),
          );
          dispatch(uiActions.thinkingEnded());
          return;
        } catch (error) {
          lastError =
            error instanceof Error ? error : new Error('Unknown error');

          // If not the last attempt, wait before retrying
          if (attempt < maxRetries - 1) {
            await new Promise((resolve, reject) => {
              const timer = setTimeout(resolve, baseDelay * (attempt + 1));
              signal?.addEventListener(
                'abort',
                () => {
                  clearTimeout(timer);
                  reject(new DOMException('Aborted', 'AbortError'));
                },
                { once: true },
              );
            }).catch(() => {
              /* abort handled by signal check on next iteration */
            });
          }
        }
      }

      if (signal?.aborted) return;

      // All retries failed
      dispatch(uiActions.thinkingEnded());
      dispatch(
        uiActions.errorOccurred(
          'EXPLORATION_NOT_FOUND',
          lastError?.message || 'Failed to load exploration',
          true,
        ),
      );
      throw lastError;
    },
    [dispatch, sessionId],
  );

  const sendMessage = useCallback(
    async (
      content: string,
      leafId?: string,
      explorationId?: string,
    ): Promise<void> => {
      if (!sessionId) {
        throw new Error('No active session');
      }
      if (leafId && !explorationId) {
        throw new Error(
          'sendMessage: explorationId is required when leafId is set',
        );
      }

      // Tag the action surface so SSE events without scope (notably the
      // backend's `thinking` events) can be filtered to the originating tab.
      dispatch(uiActions.lastActionTabSet(leafId ? 'leaf' : 'chat'));

      // Optimistically add user message to conversation if in a leaf
      if (leafId && explorationId) {
        const userMessage = {
          id: crypto.randomUUID(),
          role: 'user' as const,
          type: 'followup' as const,
          content,
          timestamp: new Date().toISOString(),
        };
        dispatch(
          conversationActions.messageAdded(explorationId, leafId, userMessage),
        );
      }

      // Clear suggested questions immediately
      dispatch(uiActions.suggestedQuestionsCleared());

      dispatch(
        uiActions.thinkingStarted('generating', 'Antwort wird generiert...'),
      );

      try {
        await explorationApi.sendMessage(sessionId, {
          content,
          explorationContext:
            explorationId && leafId ? { explorationId, leafId } : null,
        });
      } catch (error) {
        dispatch(uiActions.thinkingEnded());
        dispatch(
          uiActions.errorOccurred(
            'LLM_ERROR',
            error instanceof Error ? error.message : 'Failed to send message',
            true,
          ),
        );
        throw error;
      }
    },
    [dispatch, sessionId],
  );

  const submitChoice = useCallback(
    async (queryId: string, choice: 'summary' | 'explore'): Promise<void> => {
      if (!sessionId) {
        throw new Error('No active session');
      }

      // Choice prompts live in the chat tab; the resulting work belongs
      // to chat as well (quick summary or topic-tree generation).
      dispatch(uiActions.lastActionTabSet('chat'));
      dispatch(uiActions.choiceCleared());
      dispatch(
        uiActions.thinkingStarted(
          'planning',
          choice === 'explore'
            ? 'Themenbaum wird erstellt...'
            : 'Zusammenfassung wird generiert...',
        ),
      );

      try {
        await explorationApi.submitChoice(sessionId, { queryId, choice });
      } catch (error) {
        dispatch(uiActions.thinkingEnded());
        dispatch(
          uiActions.errorOccurred(
            'LLM_ERROR',
            error instanceof Error ? error.message : 'Failed to submit choice',
            true,
          ),
        );
        throw error;
      }
    },
    [dispatch, sessionId],
  );

  const submitDirectionChoice = useCallback(
    async (
      queryId: string,
      directions: Array<{ id: string; name: string }>,
    ): Promise<void> => {
      if (!sessionId) {
        throw new Error('No active session');
      }

      // Optimistically mark the directions message as completed in the store
      const directionNames = directions.map((d) => d.name);
      const currentMessages = useExplorationStore.getState().session.messages;
      const directionsMsg = currentMessages.find(
        (m) => m.type === 'topic_directions' && m.directionsQueryId === queryId,
      );
      if (directionsMsg) {
        dispatch(
          sessionActions.messageUpdated(directionsMsg.id, {
            selectedDirections: directionNames,
          }),
        );
      }

      // Direction selection happens in chat; resulting tree generation is
      // chat-tab work too.
      dispatch(uiActions.lastActionTabSet('chat'));
      dispatch(uiActions.topicDirectionsCleared());
      dispatch(
        uiActions.thinkingStarted('planning', 'Themenbaum wird erstellt...'),
      );

      try {
        await explorationApi.submitDirectionChoice(sessionId, {
          queryId,
          directions,
        });
      } catch (error) {
        dispatch(uiActions.thinkingEnded());
        dispatch(
          uiActions.errorOccurred(
            'LLM_ERROR',
            error instanceof Error
              ? error.message
              : 'Failed to submit direction choice',
            true,
          ),
        );
        throw error;
      }
    },
    [dispatch, sessionId],
  );

  const requestAnalysis = useCallback(
    async (explorationId: string, leafId: string): Promise<void> => {
      if (!sessionId) {
        throw new Error('No active session');
      }

      // Analysis is shown inside the leaf view.
      dispatch(uiActions.lastActionTabSet('leaf'));
      dispatch(
        uiActions.thinkingStarted('generating', 'Analyse wird erstellt...'),
      );

      try {
        await explorationApi.requestAnalysis(sessionId, explorationId, {
          leafId,
        });
      } catch (error) {
        dispatch(uiActions.thinkingEnded());
        dispatch(
          uiActions.errorOccurred(
            'LLM_ERROR',
            error instanceof Error ? error.message : 'Analysis failed',
            true,
          ),
        );
        throw error;
      }
    },
    [dispatch, sessionId],
  );

  const endExploration = useCallback(
    async (explorationId: string): Promise<void> => {
      if (!sessionId) {
        throw new Error('No active session');
      }

      dispatch(
        uiActions.thinkingStarted(
          'generating',
          'Abschlusszusammenfassung wird erstellt...',
        ),
      );

      try {
        await explorationApi.endExploration(sessionId, explorationId);
      } catch (error) {
        dispatch(uiActions.thinkingEnded());
        dispatch(
          uiActions.errorOccurred(
            'LLM_ERROR',
            error instanceof Error
              ? error.message
              : 'Failed to end exploration',
            true,
          ),
        );
        throw error;
      }
    },
    [dispatch, sessionId],
  );

  const markExplored = useCallback(
    async (explorationId: string, leafId: string): Promise<void> => {
      if (!sessionId) {
        return;
      }

      // Optimistically update the tree
      dispatch(explorationActions.leafMarkedExplored(explorationId, leafId));

      try {
        await explorationApi.markExplored(sessionId, explorationId, leafId);
      } catch (error) {
        // Silently fail - this is not critical for UX
        // The optimistic update remains (backend will sync on next load)
        console.error('Failed to mark explored:', error);
      }
    },
    [dispatch, sessionId],
  );

  return {
    createSession,
    resumeSession,
    loadExploration,
    sendMessage,
    submitChoice,
    submitDirectionChoice,
    requestAnalysis,
    endExploration,
    markExplored,
    sessionId,
  };
}
