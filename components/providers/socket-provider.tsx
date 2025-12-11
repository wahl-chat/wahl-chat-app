'use client';

import ChatSocket from '@/lib/chat-socket';
import type {
  ChatSessionInitializedPayload,
  PartyResponseChunkReadyPayload,
  PartyResponseCompletePayload,
  ProConPerspectiveReadyPayload,
  QuickRepliesAndTitleReadyPayload,
  RespondingPartiesSelectedPayload,
  SourcesReadyPayload,
  TextToSpeechCompletePayload,
  VoiceTranscribedPayload,
  VotingBehaviorCompletePayload,
  VotingBehaviorResultPayload,
  VotingBehaviorSummaryChunkPayload,
} from '@/lib/socket.types';
import { useEffect } from 'react';
import { io } from 'socket.io-client';
import { useChatStore } from './chat-store-provider';

type Props = {
  children: React.ReactNode;
};

const baseUrl = process.env.NEXT_PUBLIC_API_URL;

export const socket = io(baseUrl, {
  transports: ['websocket'],
});

const chatSocket = new ChatSocket();

function SocketProvider({ children }: Props) {
  const setSocketConnected = useChatStore((state) => state.setSocketConnected);
  const setSocket = useChatStore((state) => state.setSocket);
  const selectRespondingParties = useChatStore(
    (state) => state.selectRespondingParties,
  );
  const mergeStreamingChunkPayloadForMessage = useChatStore(
    (state) => state.mergeStreamingChunkPayloadForMessage,
  );
  const updateQuickRepliesAndTitleForCurrentStreamingMessage = useChatStore(
    (state) => state.updateQuickRepliesAndTitleForCurrentStreamingMessage,
  );
  const completeStreamingMessage = useChatStore(
    (state) => state.completeStreamingMessage,
  );
  const streamingMessageSourcesReady = useChatStore(
    (state) => state.streamingMessageSourcesReady,
  );
  const completeProConPerspective = useChatStore(
    (state) => state.completeProConPerspective,
  );
  const initializedChatSession = useChatStore(
    (state) => state.initializedChatSession,
  );
  const addVotingBehaviorSummaryChunk = useChatStore(
    (state) => state.addVotingBehaviorSummaryChunk,
  );
  const addVotingBehaviorResult = useChatStore(
    (state) => state.addVotingBehaviorResult,
  );
  const completeVotingBehavior = useChatStore(
    (state) => state.completeVotingBehavior,
  );
  const setTtsReady = useChatStore((state) => state.setTtsReady);
  const setTtsError = useChatStore((state) => state.setTtsError);
  const setVoiceTranscribed = useChatStore(
    (state) => state.setVoiceTranscribed,
  );

  useEffect(() => {
    setSocket(chatSocket);

    if (chatSocket.connected) {
      onConnect();
    }

    function onConnect() {
      setSocketConnected(true);
    }

    function onDisconnect() {
      setSocketConnected(false);
    }

    function onRespondingPartiesSelected(
      data: RespondingPartiesSelectedPayload,
    ) {
      selectRespondingParties(data.session_id, data.party_ids);
    }

    function onSourcesReady(data: SourcesReadyPayload) {
      streamingMessageSourcesReady(
        data.session_id,
        data.party_id,
        data.sources,
      );
    }

    function onPartyResponseChunkReady(data: PartyResponseChunkReadyPayload) {
      mergeStreamingChunkPayloadForMessage(
        data.session_id,
        data.party_id,
        data,
      );
    }

    function onPartyResponseComplete(data: PartyResponseCompletePayload) {
      completeStreamingMessage(
        data.session_id,
        data.party_id,
        data.complete_message,
        data.message_id,
      );
    }

    function onQuickRepliesAndTitleReady(
      data: QuickRepliesAndTitleReadyPayload,
    ) {
      updateQuickRepliesAndTitleForCurrentStreamingMessage(
        data.session_id,
        data.quick_replies,
        data.title,
      );
    }

    function onProConPerspectiveReady(data: ProConPerspectiveReadyPayload) {
      completeProConPerspective(data.request_id, data.message);
    }

    function onChatSessionInitialized(data: ChatSessionInitializedPayload) {
      initializedChatSession(data.session_id);
    }

    function onVotingBehaviorSummaryChunk(
      data: VotingBehaviorSummaryChunkPayload,
    ) {
      addVotingBehaviorSummaryChunk(
        data.request_id,
        data.summary_chunk,
        data.is_end,
      );
    }

    function onVotingBehaviorResult(data: VotingBehaviorResultPayload) {
      addVotingBehaviorResult(data.request_id, data.vote, data.is_end);
    }

    function onVotingBehaviorComplete(data: VotingBehaviorCompletePayload) {
      completeVotingBehavior(data.request_id, data.votes, data.message);
    }

    function onTextToSpeechComplete(data: TextToSpeechCompletePayload) {
      if (data.status.indicator === 'success') {
        setTtsReady(data.party_id, data.message_id, data.audio_base64);
      } else {
        setTtsError(data.party_id, data.message_id, data.status.message);
      }
    }

    function onVoiceTranscribed(data: VoiceTranscribedPayload) {
      setVoiceTranscribed(
        data.grouped_message_id,
        data.message_id,
        data.transcribed_text,
      );
    }

    chatSocket.on('connect', onConnect);
    chatSocket.on('disconnect', onDisconnect);
    chatSocket.on('responding_parties_selected', onRespondingPartiesSelected);
    chatSocket.on('chat_session_initialized', onChatSessionInitialized);
    chatSocket.on('sources_ready', onSourcesReady);
    chatSocket.on('party_response_chunk_ready', onPartyResponseChunkReady);
    chatSocket.on('party_response_complete', onPartyResponseComplete);
    chatSocket.on('quick_replies_and_title_ready', onQuickRepliesAndTitleReady);
    chatSocket.on('pro_con_perspective_complete', onProConPerspectiveReady);
    chatSocket.on(
      'voting_behavior_summary_chunk',
      onVotingBehaviorSummaryChunk,
    );
    chatSocket.on('voting_behavior_result', onVotingBehaviorResult);
    chatSocket.on('voting_behavior_complete', onVotingBehaviorComplete);
    chatSocket.on('text_to_speech_complete', onTextToSpeechComplete);
    chatSocket.on('voice_transcribed', onVoiceTranscribed);

    return () => {
      chatSocket.off('connect', onConnect);
      chatSocket.off('disconnect', onDisconnect);
      chatSocket.off(
        'responding_parties_selected',
        onRespondingPartiesSelected,
      );
      chatSocket.off('chat_session_initialized', onChatSessionInitialized);
      chatSocket.off('sources_ready', onSourcesReady);
      chatSocket.off('party_response_chunk_ready', onPartyResponseChunkReady);
      chatSocket.off('party_response_complete', onPartyResponseComplete);
      chatSocket.off(
        'quick_replies_and_title_ready',
        onQuickRepliesAndTitleReady,
      );
      chatSocket.off('pro_con_perspective_complete', onProConPerspectiveReady);
      chatSocket.off(
        'voting_behavior_summary_chunk',
        onVotingBehaviorSummaryChunk,
      );
      chatSocket.off('voting_behavior_result', onVotingBehaviorResult);
      chatSocket.off('voting_behavior_complete', onVotingBehaviorComplete);
      chatSocket.off('text_to_speech_complete', onTextToSpeechComplete);
      chatSocket.off('voice_transcribed', onVoiceTranscribed);
    };
  }, [
    selectRespondingParties,
    mergeStreamingChunkPayloadForMessage,
    setSocket,
    setSocketConnected,
    updateQuickRepliesAndTitleForCurrentStreamingMessage,
    completeStreamingMessage,
    streamingMessageSourcesReady,
    completeProConPerspective,
    initializedChatSession,
    addVotingBehaviorSummaryChunk,
    addVotingBehaviorResult,
    completeVotingBehavior,
    setTtsReady,
    setTtsError,
    setVoiceTranscribed,
  ]);

  return <>{children}</>;
}

export default SocketProvider;
