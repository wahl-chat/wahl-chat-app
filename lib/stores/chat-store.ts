import { DEFAULT_LLM_SIZE } from '@/lib/firebase/firebase.types';
import { devtools } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import { createStore } from 'zustand/vanilla';
import { addVotingBehaviorResult } from './actions/add-voting-behavior-result';
import { addVotingBehaviorSummaryChunk } from './actions/add-voting-behavior-summary-chunk';
import { cancelStreamingMessages } from './actions/cancel-streaming-messages';
import { chatAddUserMessage } from './actions/chat-add-user-message';
import { completeProConPerspective } from './actions/complete-pro-con-perspective';
import { completeStreamingMessage } from './actions/complete-streaming-message';
import { completeVotingBehavior } from './actions/complete-voting-behavior';
import { generateProConPerspective } from './actions/generate-pro-con-perspective';
import { generateSharingSnapshotLink } from './actions/generate-sharing-snapshot-link';
import { generateVotingBehaviorSummary } from './actions/generate-voting-behavior-summary';
import { hydrateChatSession } from './actions/hydrate-chat-session';
import { initializeChatSession } from './actions/initialize-chat-session';
import { initializedChatSession } from './actions/initialized-chat-session';
import { loadChatSession } from './actions/load-chat-session';
import { mergeStreamingChunkPayloadForMessage } from './actions/merge-streaming-chunk-payload-for-message';
import { newChat } from './actions/new-chat';
import { selectRespondingParties } from './actions/select-responding-parties';
import { setChatSessionId } from './actions/set-chat-session-id';
import { setChatSessionIsPublic } from './actions/set-chat-session-is-public';
import { setInput } from './actions/set-input';
import { setMessageFeedback } from './actions/set-message-feedback';
import { setPartyIds } from './actions/set-party-ids';
import { setPreSelectedParties } from './actions/set-pre-selected-parties';
import { setSocket } from './actions/set-socket';
import { setSocketConnected } from './actions/set-socket-connected';
import { setSocketConnecting } from './actions/set-socket-connecting';
import { setSocketError } from './actions/set-socket-error';
import { startTimeoutForStreamingMessages } from './actions/start-timeout-for-streaming-messages';
import { streamingMessageSourcesReady } from './actions/streaming-message-sources-ready';
import { updateQuickRepliesAndTitleForCurrentStreamingMessage } from './actions/update-quick-replies-and-title-for-current-streaming-message';
import type { ChatStore, ChatStoreState } from './chat-store.types';

export const SURVEY_BANNER_MIN_MESSAGE_COUNT = 8;

const defaultState: ChatStoreState = {
  userId: undefined,
  isAnonymous: true,
  chatSessionId: undefined,
  localPreliminaryChatSessionId: undefined,
  partyIds: new Set(),
  messages: [],
  input: '',
  loading: {
    general: false,
    initializingChatSocketSession: false,
    chatSession: false,
    proConPerspective: undefined,
    newMessage: false,
    votingBehaviorSummary: undefined,
  },
  pendingStreamingMessageTimeoutHandler: {},
  error: undefined,
  initialQuestionError: undefined,
  currentQuickReplies: [],
  currentChatTitle: undefined,
  chatSessionIsPublic: false,
  preSelectedParties: undefined,
  socket: {},
  currentStreamingMessages: undefined,
  tenant: undefined,
};

export function createChatStore(initialState?: Partial<ChatStore>) {
  return createStore<ChatStore>()(
    devtools(
      immer((set, get) => ({
        ...defaultState,
        ...initialState,
        setIsAnonymous: (isAnonymous: boolean) => set({ isAnonymous }),
        setInput: setInput(get, set),
        addUserMessage: chatAddUserMessage(get, set),
        setChatSessionId: setChatSessionId(get, set),
        newChat: newChat(get, set),
        selectRespondingParties: selectRespondingParties(get, set),
        loadChatSession: loadChatSession(get, set),
        hydrateChatSession: hydrateChatSession(get, set),
        generateProConPerspective: generateProConPerspective(get, set),
        setChatSessionIsPublic: setChatSessionIsPublic(get, set),
        setMessageFeedback: setMessageFeedback(get, set),
        setPreSelectedParties: setPreSelectedParties(get, set),
        setSocket: setSocket(get, set),
        setSocketConnecting: setSocketConnecting(get, set),
        setSocketConnected: setSocketConnected(get, set),
        setSocketError: setSocketError(get, set),
        initializeChatSession: initializeChatSession(get, set),
        initializedChatSession: initializedChatSession(get, set),
        streamingMessageSourcesReady: streamingMessageSourcesReady(get, set),
        mergeStreamingChunkPayloadForMessage:
          mergeStreamingChunkPayloadForMessage(get, set),
        updateQuickRepliesAndTitleForCurrentStreamingMessage:
          updateQuickRepliesAndTitleForCurrentStreamingMessage(get, set),
        completeStreamingMessage: completeStreamingMessage(get, set),
        cancelStreamingMessages: cancelStreamingMessages(get, set),
        startTimeoutForStreamingMessages: startTimeoutForStreamingMessages(
          get,
          set,
        ),
        completeProConPerspective: completeProConPerspective(get, set),
        generateSharingSnapshotLink: generateSharingSnapshotLink(get, set),
        generateVotingBehaviorSummary: generateVotingBehaviorSummary(get, set),
        addVotingBehaviorResult: addVotingBehaviorResult(get, set),
        addVotingBehaviorSummaryChunk: addVotingBehaviorSummaryChunk(get, set),
        completeVotingBehavior: completeVotingBehavior(get, set),
        setPartyIds: setPartyIds(get, set),
        getLLMSize: () => get().tenant?.llm_size ?? DEFAULT_LLM_SIZE,
      })),
    ),
  );
}
