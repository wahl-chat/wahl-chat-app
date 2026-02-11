import type { SwiperMessage } from './wahl-swiper-store.types';

export type AddUserMessagePayload = {
  chat_history: SwiperMessage[];
  current_title: string;
  user_message: string;
  current_political_question: string;
};

export type AddUserMessageResponse = {
  message: SwiperMessage;
  title: string;
  quick_replies: string[];
};
