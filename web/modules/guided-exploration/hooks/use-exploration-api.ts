/**
 * useExplorationApi Hook
 * Provides typed API methods with store integration
 */

'use client';

import { useParams } from 'next/navigation';
import { useCallback } from 'react';

import { explorationApi } from '@/modules/guided-exploration/services/exploration-api';
import {
  connectionActions,
  conversationActions,
  explorationActions,
  selectExplorationId,
  selectSessionId,
  sessionActions,
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import { buildBreadcrumb } from '@/modules/guided-exploration/utils';

export interface UseExplorationApiReturn {
  /** Create a new session and connect */
  createSession: () => Promise<string>;

  /** Load an existing session */
  resumeSession: (sessionId: string) => Promise<void>;

  /** Load a specific exploration */
  loadExploration: (explorationId: string) => Promise<void>;

  /** Send a message or question */
  sendMessage: (content: string, leafId?: string) => Promise<void>;

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

  /** Navigate to a path in the tree */
  navigate: (targetPath: string[]) => Promise<void>;

  /** Request analysis for current leaf */
  requestAnalysis: (leafId: string) => Promise<void>;

  /** End the current exploration */
  endExploration: () => Promise<void>;

  /** Request PDF export */
  requestExport: (
    includeAnalysis: boolean,
    includeUnexplored: boolean,
  ) => Promise<string>;

  /** Get export download URL */
  getExportUrl: (exportId: string) => string;

  /** Mark a leaf as explored */
  markExplored: (leafId: string) => Promise<void>;

  /** Current session ID */
  sessionId: string | null;

  /** Current exploration ID */
  explorationId: string | null;
}

/**
 * Hook providing API methods integrated with the store
 */
export function useExplorationApi(): UseExplorationApiReturn {
  const params = useParams();
  const contextId = params.contextId as string;
  const dispatch = useExplorationStore((s) => s.dispatch);
  const sessionId = useExplorationStore(selectSessionId);
  const explorationId = useExplorationStore(selectExplorationId);

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

        dispatch(
          sessionActions.loaded(
            response.sessionId,
            response.activeExploration?.id,
          ),
        );
        // Load session messages into the store
        if (response.messages && response.messages.length > 0) {
          dispatch(sessionActions.messagesLoaded(response.messages));
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
    async (expId: string): Promise<void> => {
      if (!sessionId) {
        throw new Error('No active session');
      }

      dispatch(
        uiActions.thinkingStarted('retrieving', 'Erkundung wird geladen...'),
      );

      // Retry logic for timing issues (exploration may not be ready immediately)
      const maxRetries = 5;
      const baseDelay = 500;
      let lastError: Error | null = null;

      for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
          const response = await explorationApi.getExploration(
            sessionId,
            expId,
          );

          // Compute initial breadcrumb for root view
          const initialBreadcrumb = buildBreadcrumb(response.tree, []);

          dispatch(
            explorationActions.started(response.id, response.tree, {
              explorationId: response.id,
              currentPath: [],
              breadcrumb: initialBreadcrumb,
            }),
          );
          dispatch(uiActions.thinkingEnded());
          return;
        } catch (error) {
          lastError =
            error instanceof Error ? error : new Error('Unknown error');

          // If not the last attempt, wait before retrying
          if (attempt < maxRetries - 1) {
            await new Promise((resolve) =>
              setTimeout(resolve, baseDelay * (attempt + 1)),
            );
          }
        }
      }

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
    async (content: string, leafId?: string): Promise<void> => {
      if (!sessionId) {
        throw new Error('No active session');
      }

      // Optimistically add user message to conversation if in a leaf
      if (leafId) {
        const userMessage = {
          id: crypto.randomUUID(),
          role: 'user' as const,
          type: 'followup' as const,
          content,
          timestamp: new Date().toISOString(),
        };
        dispatch(conversationActions.messageAdded(leafId, userMessage));
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
    [dispatch, sessionId, explorationId],
  );

  const submitChoice = useCallback(
    async (queryId: string, choice: 'summary' | 'explore'): Promise<void> => {
      if (!sessionId) {
        throw new Error('No active session');
      }

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

  const navigate = useCallback(
    async (targetPath: string[]): Promise<void> => {
      if (!sessionId || !explorationId) {
        throw new Error('No active exploration');
      }

      dispatch(
        uiActions.thinkingStarted('retrieving', 'Inhalte werden geladen...'),
      );

      try {
        await explorationApi.navigate(sessionId, explorationId, { targetPath });
      } catch (error) {
        dispatch(uiActions.thinkingEnded());
        dispatch(
          uiActions.errorOccurred(
            'NAVIGATION_INVALID',
            error instanceof Error ? error.message : 'Navigation failed',
            true,
          ),
        );
        throw error;
      }
    },
    [dispatch, sessionId, explorationId],
  );

  const requestAnalysis = useCallback(
    async (leafId: string): Promise<void> => {
      if (!sessionId || !explorationId) {
        throw new Error('No active exploration');
      }

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
    [dispatch, sessionId, explorationId],
  );

  const endExploration = useCallback(async (): Promise<void> => {
    if (!sessionId || !explorationId) {
      throw new Error('No active exploration');
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
          error instanceof Error ? error.message : 'Failed to end exploration',
          true,
        ),
      );
      throw error;
    }
  }, [dispatch, sessionId, explorationId]);

  const requestExport = useCallback(
    async (
      includeAnalysis: boolean,
      includeUnexplored: boolean,
    ): Promise<string> => {
      if (!sessionId || !explorationId) {
        throw new Error('No active exploration');
      }

      try {
        const response = await explorationApi.requestExport(
          sessionId,
          explorationId,
          { includeAnalysis, includeUnexplored },
        );
        return response.exportId;
      } catch (error) {
        dispatch(
          uiActions.errorOccurred(
            'EXPORT_FAILED',
            error instanceof Error ? error.message : 'Export failed',
            true,
          ),
        );
        throw error;
      }
    },
    [dispatch, sessionId, explorationId],
  );

  const getExportUrl = useCallback(
    (exportId: string): string => {
      if (!sessionId || !explorationId) {
        throw new Error('No active exploration');
      }

      return explorationApi.getExportDownloadUrl(
        sessionId,
        explorationId,
        exportId,
      );
    },
    [sessionId, explorationId],
  );

  const markExplored = useCallback(
    async (leafId: string): Promise<void> => {
      if (!sessionId || !explorationId) {
        return;
      }

      // Optimistically update the tree
      dispatch(explorationActions.leafMarkedExplored(leafId));

      try {
        await explorationApi.markExplored(sessionId, explorationId, leafId);
      } catch (error) {
        // Silently fail - this is not critical for UX
        // The optimistic update remains (backend will sync on next load)
        console.error('Failed to mark explored:', error);
      }
    },
    [dispatch, sessionId, explorationId],
  );

  return {
    createSession,
    resumeSession,
    loadExploration,
    sendMessage,
    submitChoice,
    submitDirectionChoice,
    navigate,
    requestAnalysis,
    endExploration,
    requestExport,
    getExportUrl,
    markExplored,
    sessionId,
    explorationId,
  };
}
