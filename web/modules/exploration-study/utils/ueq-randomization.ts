/**
 * Utility for randomizing UEQ-S item order
 */

import {
  UEQ_SHORT_ITEMS,
  type UeqItem,
} from '@/modules/exploration-study/types';

/**
 * Fisher-Yates shuffle algorithm
 */
function shuffle<T>(array: T[]): T[] {
  const result = [...array];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

/**
 * Get randomized UEQ items with their order tracked
 */
export function getRandomizedUeqItems(): {
  items: UeqItem[];
  order: number[];
} {
  const indices = UEQ_SHORT_ITEMS.map((_, i) => i);
  const shuffledIndices = shuffle(indices);
  const items = shuffledIndices.map((i) => UEQ_SHORT_ITEMS[i]);

  return {
    items,
    order: shuffledIndices.map((i) => UEQ_SHORT_ITEMS[i].id),
  };
}
