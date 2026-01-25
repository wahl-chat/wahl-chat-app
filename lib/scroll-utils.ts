'use client';

import {
  SCROLL_CONTAINER_ID,
  buildProConPerspectiveSeparatorId,
  buildVotingBehaviorSeparatorId,
} from './scroll-constants';

export async function chatViewScrollToBottom({
  behavior = 'smooth',
}: {
  behavior?: 'smooth' | 'instant';
} = {}) {
  if (!document) return;

  await new Promise((resolve) => setTimeout(resolve, 0));

  const container = document.getElementById(SCROLL_CONTAINER_ID);

  if (!container) return;

  container?.scrollTo({
    top: container?.scrollHeight,
    behavior,
  });
}

export async function chatViewScrollToProConPerspectiveContainer(
  messageId: string,
) {
  if (!document) return;

  const proConPerspectiveSeparator = document.getElementById(
    buildProConPerspectiveSeparatorId(messageId),
  );

  if (!proConPerspectiveSeparator) return;

  proConPerspectiveSeparator.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  });
}

export async function chatViewScrollToVotingBehaviorContainer(
  messageId: string,
) {
  if (!document) return;

  const votingBehaviorSeparator = document.getElementById(
    buildVotingBehaviorSeparatorId(messageId),
  );

  if (!votingBehaviorSeparator) return;

  votingBehaviorSeparator.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  });
}

export function scrollToTopOfLastElementInChatScrollContainer() {
  if (!document) return;

  const scrollContainer = document.getElementById(SCROLL_CONTAINER_ID);
  const child = scrollContainer?.lastElementChild;

  if (!child) return;

  const lastElement = child.lastElementChild as HTMLElement;

  if (!lastElement) return;

  scrollContainer.scrollTo({
    top: Math.min(lastElement.offsetTop - 12, scrollContainer.scrollHeight),
    behavior: 'smooth',
  });
}

export async function scrollToCarouselContainerBottom(containerId: string) {
  if (!document) return;

  const scrollContainer = document.getElementById(SCROLL_CONTAINER_ID);
  const carouselContainer = document.getElementById(containerId);

  if (!scrollContainer || !carouselContainer) return;

  const child = scrollContainer?.lastElementChild;

  if (!child) return;

  const lastElement = child.lastElementChild as HTMLElement;

  if (!lastElement) return;

  if (lastElement === carouselContainer) {
    await new Promise((resolve) => setTimeout(resolve, 300));
  }

  scrollContainer.scrollTo({
    top: Math.min(
      carouselContainer.offsetTop - 12,
      scrollContainer.scrollHeight,
    ),
    behavior: 'smooth',
  });
}

export async function scrollMessageBottomInView(messageId: string) {
  if (!document) return;

  const scrollContainer = document.getElementById(SCROLL_CONTAINER_ID);
  const message = document.getElementById(messageId);

  if (!scrollContainer || !message) return;

  const messageHeight = message.offsetHeight;

  const isMessageBottomInView =
    message.offsetTop + messageHeight <=
    scrollContainer.scrollTop + scrollContainer.clientHeight;

  if (isMessageBottomInView) return;

  message.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function findNearestChildOfParent(
  element: HTMLElement,
  parent: HTMLElement,
): HTMLElement | null {
  let currentElement: HTMLElement | null = element;
  let nearestChild: HTMLElement | null = null;

  while (
    currentElement &&
    currentElement !== parent &&
    currentElement.parentElement !== parent
  ) {
    nearestChild = currentElement;
    currentElement = currentElement.parentElement as HTMLElement;
  }

  return nearestChild;
}

export function scrollMessageIntoView(messageId: string) {
  if (typeof document === 'undefined') return;

  const scrollContainer = document.getElementById(SCROLL_CONTAINER_ID);
  const message = document.getElementById(messageId);

  if (!scrollContainer) {
    console.warn(
      `Scroll container with ID "${SCROLL_CONTAINER_ID}" not found.`,
    );
    return;
  }

  if (!message) {
    console.warn(`Message with ID "${messageId}" not found.`);
    return;
  }

  const messageContainer = findNearestChildOfParent(message, scrollContainer);

  if (!messageContainer) return;

  scrollContainer.scrollTo({
    top: messageContainer.offsetTop - 12,
    behavior: 'instant',
  });
}
