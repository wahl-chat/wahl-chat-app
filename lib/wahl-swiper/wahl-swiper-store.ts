import { immer } from 'zustand/middleware/immer';
import { createStore } from 'zustand/vanilla';
import { saveSwiperHistory } from './actions/save-swiper-history';
import { setSwiperInput } from './actions/set-swiper-input';
import { addUserMessage } from './actions/swiper-add-user-message';
import { swiperRemoveCard } from './actions/swiper-remove-card';
import { swiperSetIsLoadingMessage } from './actions/swiper-set-is-loading-message';
import type {
  WahlSwiperStore,
  WahlSwiperStoreState,
} from './wahl-swiper-store.types';

export const SURVEY_BANNER_MIN_MESSAGE_COUNT = 8;
export const SWIPER_DEFAULT_QUICK_REPLIES = [
  'Wie ist die aktuelle Lage?',
  'Was sind Vor- und Nachteile davon?',
  'Was sind alternative Lösungen?',
];

const defaultState: WahlSwiperStoreState = {
  allTheses: [],
  thesesStack: [],
  history: {},
  messageHistory: {},
  swiperInput: {},
  isLoadingMessage: {},
  chatIsExpanded: false,
  currentQuickReplies: {},
  showSkipDisclaimer: false,
  skipDisclaimerShown: false,
};

export function createWahlOMatStore(initialState?: Partial<WahlSwiperStore>) {
  return createStore<WahlSwiperStore>()(
    immer((set, get) => ({
      ...defaultState,
      ...initialState,

      removeCard: swiperRemoveCard(get, set),
      reset: () => {
        set((state) => {
          state.thesesStack = state.allTheses;
          state.history = {};
        });
      },
      back: () => {
        set((state) => {
          state.thesesStack.push(state.allTheses[state.thesesStack.length]);
        });
      },
      addUserMessage: addUserMessage(get, set),
      setSwiperInput: setSwiperInput(get, set),
      setIsLoadingMessage: swiperSetIsLoadingMessage(get, set),
      setChatIsExpanded: (isExpanded: boolean) =>
        set({ chatIsExpanded: isExpanded }),
      getCurrentThesis: () => get().thesesStack[get().thesesStack.length - 1],
      saveSwiperHistory: saveSwiperHistory(get, set),
      setShowSkipDisclaimer: (show: boolean) =>
        set({ showSkipDisclaimer: show }),
      setSkipDisclaimerShown: (shown: boolean) =>
        set({ skipDisclaimerShown: shown }),
    })),
  );
}
