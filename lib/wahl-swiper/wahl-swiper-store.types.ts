import type { Source } from '@/lib/stores/chat-store.types';
import type { WritableDraft } from 'immer';
import type { SwipeType } from './wahl-swiper.types';

export type Thesis = {
  id: string;
  topic: string;
  question: string;
};

export type SwiperMessage = {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  sources: Source[];
};

export type WahlSwiperStoreState = {
  allTheses: Thesis[];
  thesesStack: Thesis[];
  history: Record<string, SwipeType>;
  messageHistory: Record<string, SwiperMessage[]>;
  swiperInput: Record<string, string>;
  isLoadingMessage: Record<string, boolean>;
  chatIsExpanded: boolean;
  currentQuickReplies: Record<string, string[]>;
  showSkipDisclaimer: boolean;
  skipDisclaimerShown: boolean;
};

export type WahlSwiperStoreActions = {
  removeCard: (swipe: SwipeType) => void;
  reset: () => void;
  back: () => void;
  addUserMessage: (message: string) => void;
  setSwiperInput: (input: string) => void;
  setIsLoadingMessage: (isLoading: boolean) => void;
  setChatIsExpanded: (isExpanded: boolean) => void;
  getCurrentThesis: () => Thesis | undefined;
  saveSwiperHistory: (userId: string) => Promise<string>;
  setShowSkipDisclaimer: (show: boolean) => void;
  setSkipDisclaimerShown: (shown: boolean) => void;
};

export type WahlSwiperStore = WahlSwiperStoreState & WahlSwiperStoreActions;

export type WahlSwiperStoreActionHandlerFor<
  T extends keyof WahlSwiperStoreActions,
> = (
  get: () => WahlSwiperStore,
  set: (
    nextStateOrUpdater:
      | WahlSwiperStore
      | Partial<WahlSwiperStore>
      | ((state: WritableDraft<WahlSwiperStore>) => void),
    shouldReplace?: false,
  ) => void,
) => (
  ...args: Parameters<WahlSwiperStoreActions[T]>
) => ReturnType<WahlSwiperStoreActions[T]>;
