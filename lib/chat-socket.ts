'use client';

import { socket } from '@/components/providers/socket-provider';
import type {
  AddUserMessagePayload,
  ChatSessionInitPayload,
  ChatSessionInitializedPayload,
  GenerateVotingBehaviorSummaryPayload,
  PartyResponseChunkReadyPayload,
  PartyResponseCompletePayload,
  ProConPerspectiveReadyPayload,
  ProConPerspectiveRequestPayload,
  QuickRepliesAndTitleReadyPayload,
  RespondingPartiesSelectedPayload,
  SourcesReadyPayload,
  TextToSpeechCompletePayload,
  TextToSpeechRequestPayload,
  VoiceMessageRequestPayload,
  VoiceTranscribedPayload,
  VotingBehaviorCompletePayload,
  VotingBehaviorResultPayload,
  VotingBehaviorSummaryChunkPayload,
} from './socket.types';

type ChatSocketListenerEvent = {
  connect: () => void;
  disconnect: () => void;
  chat_session_initialized: (data: ChatSessionInitializedPayload) => void;
  sources_ready: (data: SourcesReadyPayload) => void;
  party_response_chunk_ready: (data: PartyResponseChunkReadyPayload) => void;
  party_response_complete: (data: PartyResponseCompletePayload) => void;
  quick_replies_and_title_ready: (
    data: QuickRepliesAndTitleReadyPayload,
  ) => void;
  pro_con_perspective_complete: (data: ProConPerspectiveReadyPayload) => void;
  responding_parties_selected: (data: RespondingPartiesSelectedPayload) => void;
  voting_behavior_result: (data: VotingBehaviorResultPayload) => void;
  voting_behavior_summary_chunk: (
    data: VotingBehaviorSummaryChunkPayload,
  ) => void;
  voting_behavior_complete: (data: VotingBehaviorCompletePayload) => void;
  text_to_speech_complete: (data: TextToSpeechCompletePayload) => void;
  voice_transcribed: (data: VoiceTranscribedPayload) => void;
};

type ChatSocketSenderEvent = {
  chat_session_init: ChatSessionInitPayload;
  chat_answer_request: AddUserMessagePayload;
  pro_con_perspective_request: ProConPerspectiveRequestPayload;
  voting_behavior_request: GenerateVotingBehaviorSummaryPayload;
  voice_message_request: VoiceMessageRequestPayload;
  text_to_speech_request: TextToSpeechRequestPayload;
};

class ChatSocket {
  public get connected(): boolean {
    return socket.connected;
  }

  public on<T extends keyof ChatSocketListenerEvent>(
    event: T,
    callback: ChatSocketListenerEvent[T],
  ) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    socket.on(event, callback as any);
  }

  public off<T extends keyof ChatSocketListenerEvent>(
    event: T,
    callback: ChatSocketListenerEvent[T],
  ) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    socket.off(event, callback as any);
  }

  private emit<T extends keyof ChatSocketSenderEvent>(
    event: T,
    data: ChatSocketSenderEvent[T],
  ) {
    socket.emit(event, data);
  }

  public initializeChatSession(data: ChatSessionInitPayload) {
    this.emit('chat_session_init', data);
  }

  public addUserMessage(data: AddUserMessagePayload) {
    this.emit('chat_answer_request', data);
  }

  public generateProConPerspective(data: ProConPerspectiveRequestPayload) {
    this.emit('pro_con_perspective_request', data);
  }

  public generateVotingBehaviorSummary(
    data: GenerateVotingBehaviorSummaryPayload,
  ) {
    this.emit('voting_behavior_request', data);
  }

  public sendVoiceMessage(data: VoiceMessageRequestPayload) {
    this.emit('voice_message_request', data);
  }

  public requestTextToSpeech(data: TextToSpeechRequestPayload) {
    this.emit('text_to_speech_request', data);
  }
}

export default ChatSocket;
