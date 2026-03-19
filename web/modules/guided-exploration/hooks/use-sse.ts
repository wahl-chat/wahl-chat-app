/**
 * useSSE Hook
 * Connects SSE events to the exploration store
 */

'use client';

import { useCallback, useEffect, useRef } from 'react';

import { explorationApi } from '@/modules/guided-exploration/services/exploration-api';
import {
  type SSEClient,
  createSSEClient,
} from '@/modules/guided-exploration/services/sse-client';
import {
  connectionActions,
  conversationActions,
  explorationActions,
  sessionActions,
  streamActions,
  summaryActions,
  uiActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import type {
  AnalysisResultEvent,
  ChatMessageEvent,
  ChoicePromptEvent,
  ConversationMessageEvent,
  ConversationOpenedEvent,
  ErrorEvent,
  ExplorationCompleteEvent,
  ExplorationReadyEvent,
  QuickSummaryEvent,
  SSEEvent,
  SessionClaimedEvent,
  SessionMessage,
  StreamChunkEvent,
  StreamEndEvent,
  SummaryGeneratingEvent,
  ThinkingEvent,
  TopicOverviewEvent,
  TopicTreeEvent,
} from '@/modules/guided-exploration/types';

export interface UseSSEOptions {
  /** Whether to auto-connect when sessionId changes */
  autoConnect?: boolean;
}

export interface UseSSEReturn {
  /** Connect to SSE stream */
  connect: (sessionId: string) => void;
  /** Disconnect from SSE stream */
  disconnect: () => void;
  /** Reconnect with state restoration */
  reconnect: () => Promise<void>;
  /** Check if connected */
  isConnected: boolean;
  /** Whether session was claimed by another tab */
  isSessionClaimed: boolean;
}

/**
 * Hook to manage SSE connection and dispatch events to store
 */
export function useSSE(options: UseSSEOptions = {}): UseSSEReturn {
  const { autoConnect = true } = options;

  const dispatch = useExplorationStore((s) => s.dispatch);
  const sessionId = useExplorationStore((s) => s.session.sessionId);
  const connectionStatus = useExplorationStore((s) => s.connection.status);
  const sessionClaimed = useExplorationStore(
    (s) => s.connection.sessionClaimed,
  );

  const clientRef = useRef<SSEClient | null>(null);
  // Use refs for callbacks to avoid recreating the SSE client
  const dispatchRef = useRef(dispatch);
  dispatchRef.current = dispatch;

  // Event handler that dispatches to store
  const handleEvent = useCallback(
    (event: SSEEvent) => {
      switch (event.type) {
        case 'connected':
          dispatchRef.current(connectionActions.connected());
          dispatchRef.current(uiActions.announce('Verbindung hergestellt'));
          break;

        case 'session_claimed': {
          const claimedEvent = event as SessionClaimedEvent;
          dispatchRef.current(
            connectionActions.sessionClaimed(claimedEvent.message),
          );
          dispatchRef.current(
            uiActions.announce(
              claimedEvent.message ??
                'Sitzung wurde in einem anderen Tab geöffnet',
            ),
          );
          // Disconnect the client since another tab claimed the session
          clientRef.current?.disconnect();
          break;
        }

        case 'thinking':
          dispatchRef.current(
            uiActions.thinkingStarted(
              (event as ThinkingEvent).stage,
              (event as ThinkingEvent).message,
            ),
          );
          break;

        case 'choice_prompt':
          dispatchRef.current(
            uiActions.choicePrompted(event as ChoicePromptEvent),
          );
          break;

        case 'topic_tree': {
          const treeEvent = event as TopicTreeEvent;
          console.log(
            '[SSE] topic_tree received:',
            treeEvent.explorationId,
            'isUpdate:',
            treeEvent.isUpdate,
          );
          if (treeEvent.isUpdate) {
            dispatchRef.current(explorationActions.treeUpdated(treeEvent.tree));
          } else {
            // Use treeReceived to show preview - don't end thinking yet
            // Wait for exploration_ready event before navigating
            dispatchRef.current(
              explorationActions.treeReceived(
                treeEvent.explorationId,
                treeEvent.tree,
              ),
            );
            dispatchRef.current(
              uiActions.announce('Themenbaum wird vorbereitet'),
            );
          }
          // Don't end thinking - wait for exploration_ready
          break;
        }

        case 'exploration_ready': {
          const readyEvent = event as ExplorationReadyEvent;
          console.log('[SSE] exploration_ready received:', readyEvent);
          dispatchRef.current(
            explorationActions.ready(
              readyEvent.explorationId,
              readyEvent.topicsCount,
              readyEvent.subtopicsCount,
              readyEvent.partiesCount,
            ),
          );
          dispatchRef.current(uiActions.thinkingEnded());
          dispatchRef.current(
            uiActions.announce(
              `Exploration bereit: ${readyEvent.topicsCount} Themen, ${readyEvent.subtopicsCount} Unterthemen`,
            ),
          );
          break;
        }

        case 'topic_overview': {
          const overviewEvent = event as TopicOverviewEvent;
          dispatchRef.current(
            explorationActions.navigatedToBranch(overviewEvent.navigation),
          );
          dispatchRef.current(uiActions.thinkingEnded());
          dispatchRef.current(
            uiActions.announce(`Thema: ${overviewEvent.name}`),
          );
          break;
        }

        case 'conversation_opened': {
          const convEvent = event as ConversationOpenedEvent;
          dispatchRef.current(
            explorationActions.navigatedToLeaf(
              convEvent.leafId,
              convEvent.conversation,
              convEvent.navigation,
              convEvent.analysisAvailable,
            ),
          );
          dispatchRef.current(uiActions.thinkingEnded());
          // Set suggested questions if available
          if (
            convEvent.suggestedQuestions &&
            convEvent.suggestedQuestions.length > 0
          ) {
            dispatchRef.current(
              uiActions.suggestedQuestionsSet(convEvent.suggestedQuestions),
            );
          }
          dispatchRef.current(
            uiActions.announce(
              `Unterthema geöffnet: ${convEvent.conversation.messages.length} Nachrichten`,
            ),
          );
          break;
        }

        case 'conversation_message': {
          const msgEvent = event as ConversationMessageEvent;

          // Skip user messages — they're already added optimistically
          if (msgEvent.message.role === 'user') {
            break;
          }

          // Attach citations from event to the message
          const messageWithCitations = {
            ...msgEvent.message,
            citations: msgEvent.citations ?? msgEvent.message.citations,
          };
          // Clear stream buffer before adding final message (prevents flash)
          dispatchRef.current(streamActions.bufferCleared());
          dispatchRef.current(
            conversationActions.messageAdded(
              msgEvent.leafId,
              messageWithCitations,
            ),
          );
          // Set suggested questions if available
          if (
            msgEvent.suggestedQuestions &&
            msgEvent.suggestedQuestions.length > 0
          ) {
            dispatchRef.current(
              uiActions.suggestedQuestionsSet(msgEvent.suggestedQuestions),
            );
          }
          // End thinking after receiving a message
          dispatchRef.current(uiActions.thinkingEnded());
          if (msgEvent.navigation) {
            // Navigation command was recognized
            const path = msgEvent.navigation.currentPath;
            if (path.length === 0) {
              dispatchRef.current(
                explorationActions.navigatedToRoot(msgEvent.navigation),
              );
            } else if (path.length === 1) {
              dispatchRef.current(
                explorationActions.navigatedToBranch(msgEvent.navigation),
              );
            }
          }
          dispatchRef.current(uiActions.announce('Neue Nachricht erhalten'));
          break;
        }

        case 'summary_generating': {
          const summaryEvent = event as SummaryGeneratingEvent;
          if (summaryEvent.status === 'started') {
            dispatchRef.current(summaryActions.generating(summaryEvent.leafId));
          } else {
            dispatchRef.current(
              summaryActions.generationDone(summaryEvent.leafId),
            );
          }
          break;
        }

        case 'analysis_result': {
          const analysisEvent = event as AnalysisResultEvent;
          dispatchRef.current(
            conversationActions.analysisReceived(
              analysisEvent.leafId,
              analysisEvent.analysis,
            ),
          );
          dispatchRef.current(uiActions.announce('Analyse geladen'));
          break;
        }

        case 'quick_summary': {
          const quickEvent = event as QuickSummaryEvent;
          console.log('[SSE] quick_summary citations:', quickEvent.citations);
          dispatchRef.current(
            uiActions.quickSummaryReceived({
              queryId: quickEvent.queryId,
              originalQuery: quickEvent.originalQuery,
              text: quickEvent.text,
              citations: quickEvent.citations,
              canExploreDeeper: quickEvent.canExploreDeeper,
              suggestedQuestions: quickEvent.suggestedQuestions,
            }),
          );
          // Set suggested questions if available
          if (
            quickEvent.suggestedQuestions &&
            quickEvent.suggestedQuestions.length > 0
          ) {
            dispatchRef.current(
              uiActions.suggestedQuestionsSet(quickEvent.suggestedQuestions),
            );
          }
          dispatchRef.current(uiActions.thinkingEnded());
          break;
        }

        case 'chat_message': {
          const chatEvent = event as ChatMessageEvent;
          // Create assistant message from the event
          const message: SessionMessage = {
            id: chatEvent.messageId,
            type: 'assistant',
            content: chatEvent.content,
            citations: chatEvent.citations,
            timestamp: new Date().toISOString(),
          };
          dispatchRef.current(sessionActions.messageAdded(message));
          // Set suggested questions if available
          if (
            chatEvent.suggestedQuestions &&
            chatEvent.suggestedQuestions.length > 0
          ) {
            dispatchRef.current(
              uiActions.suggestedQuestionsSet(chatEvent.suggestedQuestions),
            );
          }
          dispatchRef.current(uiActions.thinkingEnded());
          break;
        }

        case 'stream_chunk': {
          const chunkEvent = event as StreamChunkEvent;
          // Start stream if this is first chunk
          if (chunkEvent.chunkIndex === 0) {
            console.log(
              '[SSE Handler] Raw chunk event:',
              JSON.stringify(chunkEvent),
            );
            console.log('[SSE Handler] Dispatching STREAM_STARTED with:', {
              streamId: chunkEvent.streamId,
              targetType: chunkEvent.targetType,
              targetId: chunkEvent.targetId,
            });
            // End thinking when streaming starts - show content instead of spinner
            dispatchRef.current(uiActions.thinkingEnded());
            dispatchRef.current(
              streamActions.started(
                chunkEvent.streamId,
                chunkEvent.targetType,
                chunkEvent.targetId,
              ),
            );
          }
          dispatchRef.current(
            streamActions.chunkReceived(
              chunkEvent.streamId,
              chunkEvent.chunk,
              chunkEvent.section,
            ),
          );
          break;
        }

        case 'stream_end': {
          const endEvent = event as StreamEndEvent;
          dispatchRef.current(
            streamActions.ended(endEvent.streamId, endEvent.complete),
          );
          // Safety: ensure thinking is ended when stream completes
          dispatchRef.current(uiActions.thinkingEnded());
          break;
        }

        case 'exploration_complete': {
          const completeEvent = event as ExplorationCompleteEvent;
          dispatchRef.current(
            uiActions.announce(
              `Exploration abgeschlossen: ${completeEvent.stats.topicsExplored} von ${completeEvent.stats.topicsTotal} Themen erkundet`,
            ),
          );
          break;
        }

        case 'error': {
          const errorEvent = event as ErrorEvent;
          dispatchRef.current(
            uiActions.errorOccurred(
              errorEvent.code,
              errorEvent.message,
              errorEvent.recoverable,
            ),
          );
          dispatchRef.current(
            uiActions.announce(`Fehler: ${errorEvent.message}`),
          );
          break;
        }

        default:
          console.warn('[SSE] Unhandled event type:', event.type, event);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- using dispatchRef for stability
    [],
  );

  // Error handler - stable reference using dispatchRef
  const handleError = useCallback((error: Error) => {
    console.error('SSE error:', error);
    dispatchRef.current(
      uiActions.errorOccurred('LLM_ERROR', error.message, true),
    );
  }, []);

  // Status change handler - stable reference using dispatchRef
  const handleStatusChange = useCallback(
    (status: 'connecting' | 'connected' | 'disconnected') => {
      switch (status) {
        case 'connecting':
          dispatchRef.current(connectionActions.connecting());
          break;
        case 'connected':
          dispatchRef.current(connectionActions.connected());
          break;
        case 'disconnected':
          dispatchRef.current(connectionActions.disconnected());
          break;
      }
    },
    [],
  );

  // Create client once on mount - callbacks are stable via refs
  useEffect(() => {
    clientRef.current = createSSEClient({
      onEvent: handleEvent,
      onError: handleError,
      onStatusChange: handleStatusChange,
    });

    return () => {
      clientRef.current?.disconnect();
      clientRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally run once
  }, []);

  // Auto-connect when sessionId changes
  useEffect(() => {
    if (autoConnect && sessionId && clientRef.current) {
      clientRef.current.connect(sessionId);
    }
  }, [autoConnect, sessionId]);

  // Connect function
  const connect = useCallback((newSessionId: string) => {
    clientRef.current?.connect(newSessionId);
  }, []);

  // Disconnect function
  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);

  // Reconnect with state restoration
  const reconnect = useCallback(async () => {
    if (!sessionId) {
      throw new Error('No session ID to reconnect');
    }

    try {
      // 1. Fetch current session state from server
      dispatchRef.current(connectionActions.connecting());
      const sessionData = await explorationApi.getSession(sessionId);

      // 2. Restore exploration state if there was an active exploration
      if (sessionData.activeExploration) {
        const { id } = sessionData.activeExploration;
        dispatchRef.current(sessionActions.loaded(sessionId, id));
      }

      // 3. Reconnect to SSE stream
      clientRef.current?.connect(sessionId);

      dispatchRef.current(uiActions.announce('Verbindung wiederhergestellt'));
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Reconnection failed';
      dispatchRef.current(connectionActions.disconnected(message));
      dispatchRef.current(
        uiActions.errorOccurred(
          'LLM_ERROR',
          `Wiederverbindung fehlgeschlagen: ${message}`,
          true,
        ),
      );
      throw error;
    }
  }, [sessionId]);

  return {
    connect,
    disconnect,
    reconnect,
    isConnected: connectionStatus === 'connected',
    isSessionClaimed: sessionClaimed,
  };
}
