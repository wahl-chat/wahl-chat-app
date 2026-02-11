import type {
  AddUserMessagePayload,
  AddUserMessageResponse,
} from './wahl-swiper-api.types';

const baseUrl = process.env.NEXT_PUBLIC_API_URL;

export async function swiperAddUserMessage(message: AddUserMessagePayload) {
  const body = JSON.stringify(message);

  const response = await fetch(
    `${baseUrl}/api/v1/answer-wahl-chat-swiper-question`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body,
    },
  );

  if (!response.ok) {
    console.error(await response.json());

    throw new Error('Failed to add user message');
  }

  return response.json() as Promise<AddUserMessageResponse>;
}
