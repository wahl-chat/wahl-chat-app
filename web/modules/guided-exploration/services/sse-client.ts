/**
 * SSE Client
 * Manages Server-Sent Events connection for real-time updates
 */

import type { SSEEvent } from '@/modules/guided-exploration/types';
import { keysToCamelCase } from '@/modules/guided-exploration/utils/case-conversion';

export type SSEEventHandler = (event: SSEEvent) => void;
export type SSEErrorHandler = (error: Error) => void;
export type SSEStatusHandler = (
  status: 'connecting' | 'connected' | 'disconnected',
) => void;

export interface SSEClientOptions {
  /** Handler for incoming events */
  onEvent: SSEEventHandler;
  /** Handler for errors */
  onError?: SSEErrorHandler;
  /** Handler for connection status changes */
  onStatusChange?: SSEStatusHandler;
  /** Maximum reconnection attempts (default: 5) */
  maxReconnectAttempts?: number;
  /** Base delay between reconnection attempts in ms (default: 1000) */
  reconnectBaseDelay?: number;
  /** Maximum delay between reconnection attempts in ms (default: 30000) */
  reconnectMaxDelay?: number;
}

export class SSEClient {
  private eventSource: EventSource | null = null;
  private sessionId: string | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isManualClose = false;

  private readonly onEvent: SSEEventHandler;
  private readonly onError?: SSEErrorHandler;
  private readonly onStatusChange?: SSEStatusHandler;
  private readonly maxReconnectAttempts: number;
  private readonly reconnectBaseDelay: number;
  private readonly reconnectMaxDelay: number;

  constructor(options: SSEClientOptions) {
    this.onEvent = options.onEvent;
    this.onError = options.onError;
    this.onStatusChange = options.onStatusChange;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 5;
    this.reconnectBaseDelay = options.reconnectBaseDelay ?? 1000;
    this.reconnectMaxDelay = options.reconnectMaxDelay ?? 30000;
  }

  /**
   * Connect to SSE stream for a session
   */
  connect(sessionId: string): void {
    if (this.eventSource) {
      this.disconnect();
    }

    this.sessionId = sessionId;
    this.isManualClose = false;
    this.reconnectAttempts = 0;

    this.establishConnection();
  }

  /**
   * Disconnect from SSE stream
   */
  disconnect(): void {
    this.isManualClose = true;
    this.clearReconnectTimer();

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    this.onStatusChange?.('disconnected');
  }

  /**
   * Check if currently connected
   */
  isConnected(): boolean {
    return this.eventSource?.readyState === EventSource.OPEN;
  }

  /**
   * Get current session ID
   */
  getSessionId(): string | null {
    return this.sessionId;
  }

  private establishConnection(): void {
    if (!this.sessionId) return;

    this.onStatusChange?.('connecting');

    const baseUrl = process.env.NEXT_PUBLIC_API_URL;
    const url = `${baseUrl}/api/v1/guided-exploration/sessions/${this.sessionId}/stream`;

    this.eventSource = new EventSource(url);

    this.eventSource.onopen = () => {
      this.reconnectAttempts = 0;
      this.onStatusChange?.('connected');
    };

    this.eventSource.onerror = () => {
      // EventSource automatically reconnects, but we want custom control
      if (this.eventSource?.readyState === EventSource.CLOSED) {
        this.handleDisconnect();
      } else {
        this.onError?.(new Error('SSE connection error'));
      }
    };

    // Register handlers for all event types
    this.registerEventHandlers();
  }

  private registerEventHandlers(): void {
    if (!this.eventSource) return;

    const eventTypes = [
      'connected',
      'session_claimed',
      'thinking',
      'choice_prompt',
      'topic_tree',
      'topic_overview',
      'conversation_opened',
      'conversation_message',
      'summary_generating',
      'analysis_result',
      'quick_summary',
      'chat_message',
      'stream_chunk',
      'stream_end',
      'exploration_ready',
      'exploration_complete',
      'export_ready',
      'error',
    ];

    for (const eventType of eventTypes) {
      this.eventSource.addEventListener(eventType, (event: MessageEvent) => {
        try {
          const rawData = JSON.parse(event.data);
          // Convert snake_case to camelCase
          const data = keysToCamelCase<Record<string, unknown>>(rawData);
          console.log(`[SSE] received ${eventType}:`, data);
          this.onEvent({ type: eventType, ...data } as SSEEvent);
        } catch (e) {
          console.error(`[SSE] failed to parse ${eventType}:`, e, event.data);
          this.onError?.(new Error(`Failed to parse SSE event: ${eventType}`));
        }
      });
    }

    // Also handle generic message events (fallback)
    this.eventSource.onmessage = (event: MessageEvent) => {
      try {
        const rawData = JSON.parse(event.data);
        // Convert snake_case to camelCase
        const data = keysToCamelCase<SSEEvent>(rawData);
        if (data.type) {
          this.onEvent(data);
        }
      } catch {
        // Ignore parse errors for generic messages
      }
    };
  }

  private handleDisconnect(): void {
    this.eventSource = null;
    this.onStatusChange?.('disconnected');

    if (this.isManualClose) return;

    // Attempt reconnection with exponential backoff
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.scheduleReconnect();
    } else {
      this.onError?.(
        new Error(
          `Failed to reconnect after ${this.maxReconnectAttempts} attempts`,
        ),
      );
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    // Exponential backoff with jitter
    const delay = Math.min(
      this.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts) +
        Math.random() * 1000,
      this.reconnectMaxDelay,
    );

    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      if (!this.isManualClose && this.sessionId) {
        this.establishConnection();
      }
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

/**
 * Create a new SSE client instance
 */
export function createSSEClient(options: SSEClientOptions): SSEClient {
  return new SSEClient(options);
}
