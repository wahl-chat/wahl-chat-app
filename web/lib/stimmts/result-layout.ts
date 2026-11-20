/**
 * Which optional parts the result screen shows. Kept apart from the
 * component so the rules read in one place.
 */
export function resultSections({
  cast,
  chatEnabled,
  preview,
}: {
  /** Today's Stimmkarte is in the urn. */
  cast: boolean;
  /** The chat switch (`STIMMTS_CHAT_ENABLED`). */
  chatEnabled: boolean;
  /** The server-decided preview mode of the page. */
  preview: boolean;
}) {
  return {
    // Until the card is cast, the Stimmkarte itself shows the score; the
    // bottom card would repeat it.
    scoreRow: cast,
    // Preview shows the card ahead of the switch so it can be reviewed.
    chatCard: chatEnabled || preview,
  };
}
