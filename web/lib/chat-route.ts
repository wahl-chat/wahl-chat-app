type ChatSessionUrlOptions = {
  contextId: string;
  question?: string;
  partyIds?: string[];
};

export function buildChatSessionUrl({
  contextId,
  question,
  partyIds = [],
}: ChatSessionUrlOptions): string {
  const searchParams = new URLSearchParams();

  if (question) searchParams.set('q', question);
  partyIds.forEach((partyId) => searchParams.append('party_id', partyId));

  const query = searchParams.toString();
  const path = `/${encodeURIComponent(contextId)}/session`;

  return query ? `${path}?${query}` : path;
}
