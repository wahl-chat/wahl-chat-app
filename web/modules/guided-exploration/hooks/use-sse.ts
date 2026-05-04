/**
 * useSSE Hook
 * Connects SSE events to the exploration store
 */

'use client';

import { useCallback, useEffect, useMemo, useRef } from 'react';

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
  Citation,
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
  SubtopicContent,
  SummaryGeneratingEvent,
  ThinkingEvent,
  TopicDirectionsEvent,
  TopicSwitchSuggestedEvent,
  TopicTreeEvent,
} from '@/modules/guided-exploration/types';
import { findNode } from '@/modules/guided-exploration/utils/tree-helpers';

const CLIENT_ID_STORAGE_KEY = 'guided-exploration:client-id';

// One stable id per browser tab (sessionStorage), reused across StrictMode
// remounts and EventSource auto-reconnects. The backend uses it to tell a
// same-tab reconnect (silent replace) apart from a real cross-tab claim
// (session_claimed event).
function getOrCreateClientId(): string {
  if (typeof window === 'undefined') return '';
  const existing = window.sessionStorage.getItem(CLIENT_ID_STORAGE_KEY);
  if (existing) return existing;
  const fresh = crypto.randomUUID();
  window.sessionStorage.setItem(CLIENT_ID_STORAGE_KEY, fresh);
  return fresh;
}

// Backend occasionally emits the same source twice in the citations array
// (one reference per party position that quotes it). Deduplicate by id so
// downstream consumers can safely use the id as a React key.
function dedupeCitations<T extends { id: string } = Citation>(
  citations: readonly T[] | undefined,
): T[] | undefined {
  if (!citations) return citations;
  const seen = new Set<string>();
  const unique: T[] = [];
  for (const c of citations) {
    if (seen.has(c.id)) continue;
    seen.add(c.id);
    unique.push(c);
  }
  return unique;
}

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

  const clientId = useMemo(() => getOrCreateClientId(), []);
  const clientRef = useRef<SSEClient | null>(null);
  // Use refs for callbacks to avoid recreating the SSE client
  const dispatchRef = useRef(dispatch);
  dispatchRef.current = dispatch;

  // Tracks the active leaf scope for the current leaf-targeted stream.
  // Stamped on stream_chunk(chunkIndex===0) and read by follow-up events
  // that lack their own explorationId (conversation_message, analysis_result,
  // topic_switch_suggested). Persists past stream_end so late-arriving
  // conversation_message events still resolve their owning exploration even
  // after the user closes the sidebar.
  const leafStreamScopeRef = useRef<{
    explorationId: string;
    leafId: string;
  } | null>(null);

  // Resolve the explorationId for a leaf-scoped event that doesn't carry
  // one. Prefer the streaming snapshot, fall back to currently-open leaf.
  const resolveLeafScope = useCallback((leafId: string): string | null => {
    const scope = leafStreamScopeRef.current;
    if (scope && scope.leafId === leafId) return scope.explorationId;
    const active = useExplorationStore.getState().exploration.activeLeaf;
    if (active && active.leafId === leafId) return active.explorationId;
    // Last resort: scan trees for a node with this id (path-based ids
    // include the topic ancestry, so collisions across trees are unlikely).
    const trees = useExplorationStore.getState().exploration.trees;
    for (const eid of Object.keys(trees)) {
      const tree = trees[eid];
      if (tree && findNode(tree, leafId)) return eid;
    }
    return null;
  }, []);

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
          // The backend only emits session_claimed for a genuine cross-tab
          // claim (different client_id). Stop reconnecting — the new tab
          // is now the canonical session.
          clientRef.current?.disconnect();
          break;
        }

        case 'thinking':
          // Backend `thinking` events carry no scope. Let the reducer fall
          // back to `lastActionTab` (set by the user-action site) so the
          // indicator only shows on its own surface.
          dispatchRef.current(
            uiActions.thinkingStarted(
              (event as ThinkingEvent).stage,
              (event as ThinkingEvent).message,
            ),
          );
          break;

        case 'choice_prompt':
          // Choice prompts (summarize-vs-explore) are always chat-tab events.
          dispatchRef.current(
            uiActions.choicePrompted(event as ChoicePromptEvent, 'chat'),
          );
          break;

        case 'topic_tree': {
          const treeEvent = event as TopicTreeEvent;
          const existing =
            useExplorationStore.getState().exploration.trees[
              treeEvent.explorationId
            ];
          if (existing) {
            // Update only — preserve in-flight conversations.
            dispatchRef.current(
              explorationActions.treeReceived(treeEvent.tree),
            );
          } else {
            // First sighting of this exploration — initialize trees + status.
            dispatchRef.current(
              explorationActions.started(
                treeEvent.explorationId,
                treeEvent.tree,
                'active',
              ),
            );
          }
          dispatchRef.current(
            uiActions.announce('Themenbaum wird vorbereitet'),
          );
          // Don't end thinking - wait for exploration_ready
          break;
        }

        case 'exploration_ready': {
          const readyEvent = event as ExplorationReadyEvent;
          dispatchRef.current(
            explorationActions.ready(
              readyEvent.explorationId,
              readyEvent.topicsCount,
              readyEvent.subtopicsCount,
              readyEvent.partiesCount,
            ),
          );
          // Add exploration_start message to chat so the user can click to enter
          const tree =
            useExplorationStore.getState().exploration.trees[
              readyEvent.explorationId
            ] ?? null;
          const explorationMessage: SessionMessage = {
            id: crypto.randomUUID(),
            type: 'exploration_start',
            content: null,
            explorationId: readyEvent.explorationId,
            explorationQuery: tree?.originalQuery ?? undefined,
            timestamp: new Date().toISOString(),
          };
          dispatchRef.current(sessionActions.messageAdded(explorationMessage));
          dispatchRef.current(uiActions.thinkingEnded());
          dispatchRef.current(
            uiActions.announce(
              `Exploration bereit: ${readyEvent.topicsCount} Bereiche, ${readyEvent.subtopicsCount} Vergleichspunkte`,
            ),
          );
          break;
        }

        case 'conversation_opened': {
          const convEvent = event as ConversationOpenedEvent;
          const explorationId =
            convEvent.navigation?.explorationId ??
            resolveLeafScope(convEvent.leafId);
          if (!explorationId) {
            console.warn(
              '[SSE] conversation_opened without explorationId',
              convEvent,
            );
            break;
          }
          const dedupedConversation = {
            ...convEvent.conversation,
            messages: convEvent.conversation.messages.map((m) => {
              if (
                m.type !== 'initial_content' ||
                typeof m.content === 'string'
              ) {
                return m;
              }
              const sub = m.content as SubtopicContent;
              return {
                ...m,
                content: {
                  ...sub,
                  citations: dedupeCitations(sub.citations) ?? sub.citations,
                },
              };
            }),
          };
          dispatchRef.current(
            explorationActions.leafOpened(
              explorationId,
              convEvent.leafId,
              dedupedConversation,
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
              uiActions.suggestedQuestionsSet(
                convEvent.suggestedQuestions,
                'leaf',
              ),
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

          const explorationId =
            msgEvent.navigation?.explorationId ??
            resolveLeafScope(msgEvent.leafId);
          if (!explorationId) {
            console.warn(
              '[SSE] conversation_message without resolvable explorationId',
              msgEvent,
            );
            break;
          }

          // Attach citations from event to the message, deduped so the
          // citations list doesn't render two <li>s with the same key.
          const messageWithCitations = {
            ...msgEvent.message,
            citations: dedupeCitations(
              msgEvent.citations ?? msgEvent.message.citations,
            ),
          };
          // Clear stream buffer before adding final message (prevents flash)
          dispatchRef.current(streamActions.bufferCleared());
          dispatchRef.current(
            conversationActions.messageAdded(
              explorationId,
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
              uiActions.suggestedQuestionsSet(
                msgEvent.suggestedQuestions,
                'leaf',
              ),
            );
          }
          // End thinking after receiving a message
          dispatchRef.current(uiActions.thinkingEnded());
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
          const explorationId = resolveLeafScope(analysisEvent.leafId);
          if (!explorationId) {
            console.warn(
              '[SSE] analysis_result without resolvable explorationId',
              analysisEvent,
            );
            break;
          }
          dispatchRef.current(
            conversationActions.analysisReceived(
              explorationId,
              analysisEvent.leafId,
              analysisEvent.analysis,
            ),
          );
          dispatchRef.current(uiActions.announce('Analyse geladen'));
          break;
        }

        case 'quick_summary': {
          const quickEvent = event as QuickSummaryEvent;
          dispatchRef.current(
            uiActions.quickSummaryReceived({
              queryId: quickEvent.queryId,
              originalQuery: quickEvent.originalQuery,
              text: quickEvent.text,
              citations: dedupeCitations(quickEvent.citations) ?? [],
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
              uiActions.suggestedQuestionsSet(
                quickEvent.suggestedQuestions,
                'chat',
              ),
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
            citations: dedupeCitations(chatEvent.citations),
            timestamp: new Date().toISOString(),
          };
          // Clear stream buffer before adding message (prevents duplicate)
          dispatchRef.current(streamActions.bufferCleared());
          dispatchRef.current(sessionActions.messageAdded(message));
          // Set suggested questions if available
          if (
            chatEvent.suggestedQuestions &&
            chatEvent.suggestedQuestions.length > 0
          ) {
            dispatchRef.current(
              uiActions.suggestedQuestionsSet(
                chatEvent.suggestedQuestions,
                'chat',
              ),
            );
          }
          dispatchRef.current(uiActions.thinkingEnded());
          break;
        }

        case 'stream_chunk': {
          const chunkEvent = event as StreamChunkEvent;
          // Start stream if this is first chunk
          if (chunkEvent.chunkIndex === 0) {
            // End thinking when streaming starts - show content instead of spinner
            dispatchRef.current(uiActions.thinkingEnded());

            const isLeafStream =
              chunkEvent.targetType === 'initial_content' ||
              chunkEvent.targetType === 'followup' ||
              chunkEvent.targetType === 'analysis';
            const active = isLeafStream
              ? useExplorationStore.getState().exploration.activeLeaf
              : null;
            const explorationId = active?.explorationId ?? null;
            const leafId = active?.leafId ?? null;
            const originTab = isLeafStream ? 'leaf' : 'chat';

            // Snapshot scope so late-arriving leaf events still resolve
            // their explorationId after stream_end / sidebar close.
            if (isLeafStream && active) {
              leafStreamScopeRef.current = {
                explorationId: active.explorationId,
                leafId: active.leafId,
              };
            }

            dispatchRef.current(
              streamActions.started(
                chunkEvent.streamId,
                chunkEvent.targetType,
                chunkEvent.targetId,
                explorationId,
                leafId,
                originTab,
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
          // Intentionally do NOT clear leafStreamScopeRef here — the
          // conversation_message that finalizes the assistant turn often
          // arrives AFTER stream_end and still needs the scope.
          break;
        }

        case 'topic_switch_suggested': {
          const switchEvent = event as TopicSwitchSuggestedEvent;
          const explorationId = resolveLeafScope(switchEvent.leafId);
          if (!explorationId) {
            console.warn(
              '[SSE] topic_switch_suggested without resolvable explorationId',
              switchEvent,
            );
            break;
          }
          dispatchRef.current(
            uiActions.topicSwitchSuggested(
              explorationId,
              switchEvent.leafId,
              switchEvent.targetNodeId,
              switchEvent.targetNodeName,
              switchEvent.message,
            ),
          );
          break;
        }

        case 'topic_directions': {
          const directionsEvent = event as TopicDirectionsEvent;
          // Don't create a duplicate message — the backend already persists one.
          // Just check if the persisted message is already in the store
          // (it might not be if this is the live SSE flow, not a reload).
          const existingMsg = useExplorationStore
            .getState()
            .session.messages.find(
              (m) =>
                m.type === 'topic_directions' &&
                m.directionsQueryId === directionsEvent.queryId,
            );
          if (!existingMsg) {
            const directionsMessage: SessionMessage = {
              id: crypto.randomUUID(),
              type: 'topic_directions',
              content: '',
              directions: directionsEvent.directions,
              directionsQueryId: directionsEvent.queryId,
              timestamp: new Date().toISOString(),
            };
            dispatchRef.current(sessionActions.messageAdded(directionsMessage));
          }
          dispatchRef.current(
            uiActions.topicDirectionsReceived(directionsEvent),
          );
          dispatchRef.current(uiActions.thinkingEnded());
          break;
        }

        case 'exploration_complete': {
          const completeEvent = event as ExplorationCompleteEvent;
          dispatchRef.current(
            explorationActions.statusUpdated(
              completeEvent.explorationId,
              'completed',
            ),
          );
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
    [resolveLeafScope],
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

  // Stable handleEvent ref — recreates only when resolveLeafScope changes
  // (which is stable thanks to its empty dep array). The SSE client is
  // created once below.
  const handleEventRef = useRef(handleEvent);
  handleEventRef.current = handleEvent;

  // Create client once on mount - callbacks are stable via refs
  useEffect(() => {
    clientRef.current = createSSEClient({
      onEvent: (e) => handleEventRef.current(e),
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
      clientRef.current.connect(sessionId, clientId);
    }
  }, [autoConnect, sessionId, clientId]);

  // Connect function
  const connect = useCallback(
    (newSessionId: string) => {
      clientRef.current?.connect(newSessionId, clientId);
    },
    [clientId],
  );

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

      // 2. Restore session and any active exploration
      dispatchRef.current(sessionActions.loaded(sessionId));
      const activeExp = sessionData.activeExploration;
      if (activeExp) {
        dispatchRef.current(
          explorationActions.started(
            activeExp.id,
            activeExp.tree,
            activeExp.status,
          ),
        );
      }

      // 3. Reconnect to SSE stream
      clientRef.current?.connect(sessionId, clientId);

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
  }, [sessionId, clientId]);

  return {
    connect,
    disconnect,
    reconnect,
    isConnected: connectionStatus === 'connected',
    isSessionClaimed: sessionClaimed,
  };
}
