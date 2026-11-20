/**
 * Which optional parts the result screen shows. Kept apart from the
 * component so the rules read in one place.
 */
export function resultSections({
  cast,
  chatEnabled,
  chatAnswersLive,
  preview,
}: {
  /** Today's Stimmkarte is in the urn. */
  cast: boolean;
  /** The chat switch (`STIMMTS_CHAT_ENABLED`). */
  chatEnabled: boolean;
  /** The card's answers come from the general chat, not the placeholder. */
  chatAnswersLive: boolean;
  /** The server-decided preview mode of the page. */
  preview: boolean;
}) {
  return {
    // Until the card is cast, the Stimmkarte itself shows the score; the
    // bottom card would repeat it.
    scoreRow: cast,
    // Outside preview both switches must agree, so flipping the visibility
    // switch alone can never show players the placeholder answer. Preview
    // shows the card ahead of them so it can be reviewed.
    chatCard: (chatEnabled && chatAnswersLive) || preview,
  };
}
