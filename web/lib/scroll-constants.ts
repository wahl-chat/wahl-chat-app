export const SCROLL_CONTAINER_ID = 'chat-messages-container';
export const PRO_CON_PERSPECTIVE_SEPARATOR_ID_PREFIX =
  'pro-con-perspective-separator-';
export const VOTING_BEHAVIOR_SEPARATOR_ID_PREFIX = 'voting-behavior-separator-';

export function buildProConPerspectiveSeparatorId(messageId: string) {
  return PRO_CON_PERSPECTIVE_SEPARATOR_ID_PREFIX + messageId;
}

export function buildVotingBehaviorSeparatorId(messageId: string) {
  return VOTING_BEHAVIOR_SEPARATOR_ID_PREFIX + messageId;
}

export function buildCarouselContainerId(messageIds: string[]) {
  return `carousel-container-${messageIds.join('-')}`;
}
