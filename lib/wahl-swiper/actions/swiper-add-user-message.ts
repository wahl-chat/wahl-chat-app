import { generateUuid } from '@/lib/utils';
import { swiperAddUserMessage } from '@/lib/wahl-swiper/wahl-swiper-api';
import type { WahlSwiperStoreActionHandlerFor } from '@/lib/wahl-swiper/wahl-swiper-store.types';

export const addUserMessage: WahlSwiperStoreActionHandlerFor<'addUserMessage'> =
  (get, set) => async (message) => {
    const { messageHistory, getCurrentThesis } = get();

    const currentThesis = getCurrentThesis();

    if (!currentThesis) {
      return;
    }

    try {
      set((state) => {
        state.messageHistory[currentThesis.id].push({
          id: generateUuid(),
          role: 'user',
          content: message,
          sources: [],
        });

        state.isLoadingMessage[currentThesis.id] = true;
      });

      const response = await swiperAddUserMessage({
        chat_history: messageHistory[currentThesis.id],
        current_title: currentThesis.topic,
        user_message: message,
        current_political_question: currentThesis.question,
      });

      set((state) => {
        state.messageHistory[currentThesis.id].push({
          ...response.message,
          id: generateUuid(),
        });

        state.currentQuickReplies[currentThesis.id] = response.quick_replies;

        state.isLoadingMessage[currentThesis.id] = false;
      });
    } catch (error) {
      console.error(error);
    } finally {
      set((state) => ({
        isLoadingMessage: {
          ...state.isLoadingMessage,
          [currentThesis.id]: false,
        },
      }));
    }
  };
