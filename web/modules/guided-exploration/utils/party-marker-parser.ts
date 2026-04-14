/**
 * Party Marker Parser
 * Parses streaming content with [PARTY:id]...[/PARTY:id] markers
 * Handles incomplete/partial markers during streaming
 */

export interface ParsedSection {
  /** Type of section */
  type: 'intro' | 'party' | 'conclusion';
  /** Content of the section (markdown) */
  content: string;
  /** Party ID if type is 'party' */
  partyId?: string;
  /** Whether this section is still being streamed (no closing tag yet) */
  isStreaming?: boolean;
}

// Regex patterns
// Non-global version for testing existence
const PARTY_OPEN_TAG_TEST = /\[PARTY:\w+\]/;
// Global version for matching all occurrences
const PARTY_OPEN_TAG = /\[PARTY:(\w+)\]/g;
const PARTY_CLOSE_TAG = /\[\/PARTY:(\w+)\]/g;
const PARTIAL_OPEN_TAG = /\[PARTY(?::\w*)?$/;
const PARTIAL_CLOSE_TAG = /\[\/PARTY(?::\w*)?$/;
// Hide `[PARTY_BADGE`, `[PARTY_BADGE:`, `[PARTY_BADGE:sat` while streaming
// so the half-typed marker doesn't briefly leak into the rendered text.
const PARTIAL_BADGE_TAG = /\[PARTY_BADGE?(?::[\w-]*)?$|\[PARTY_BAD?G?E?$/;

/**
 * Parse content with party markers into sections.
 * Handles streaming by:
 * - Hiding partial/incomplete markers at the end
 * - Treating unclosed party sections as "streaming"
 */
export function parsePartyMarkers(content: string): ParsedSection[] {
  const sections: ParsedSection[] = [];

  // First, check for and remove any partial tag at the very end
  let cleanContent = content;
  let trailingPartial = '';

  // Check for partial opening tag at end
  const partialOpenMatch = content.match(PARTIAL_OPEN_TAG);
  if (partialOpenMatch) {
    trailingPartial = partialOpenMatch[0];
    cleanContent = content.slice(0, -trailingPartial.length);
  }

  // Check for partial closing tag at end (if no partial open)
  if (!trailingPartial) {
    const partialCloseMatch = content.match(PARTIAL_CLOSE_TAG);
    if (partialCloseMatch) {
      trailingPartial = partialCloseMatch[0];
      cleanContent = content.slice(0, -trailingPartial.length);
    }
  }

  // Check for partial party badge marker at end
  if (!trailingPartial) {
    const partialBadgeMatch = content.match(PARTIAL_BADGE_TAG);
    if (partialBadgeMatch) {
      trailingPartial = partialBadgeMatch[0];
      cleanContent = content.slice(0, -trailingPartial.length);
    }
  }

  // Now parse the clean content
  let introContent = '';

  // Find all opening and closing tags with their positions
  const openTags: Array<{ index: number; partyId: string; fullMatch: string }> =
    [];
  const closeTags: Array<{
    index: number;
    partyId: string;
    fullMatch: string;
  }> = [];

  // Use matchAll to avoid assignment in condition
  for (const match of cleanContent.matchAll(PARTY_OPEN_TAG)) {
    openTags.push({
      index: match.index,
      partyId: match[1],
      fullMatch: match[0],
    });
  }

  for (const match of cleanContent.matchAll(PARTY_CLOSE_TAG)) {
    closeTags.push({
      index: match.index,
      partyId: match[1],
      fullMatch: match[0],
    });
  }

  // If no party tags, return the whole content as intro
  if (openTags.length === 0) {
    if (cleanContent.trim()) {
      sections.push({
        type: 'intro',
        content: cleanContent,
      });
    }
    return sections;
  }

  // Process content before first party tag as intro
  if (openTags[0].index > 0) {
    introContent = cleanContent.slice(0, openTags[0].index).trim();
    if (introContent) {
      sections.push({
        type: 'intro',
        content: introContent,
      });
    }
  }

  // Process each party section
  for (let i = 0; i < openTags.length; i++) {
    const openTag = openTags[i];
    const nextOpenTag = openTags[i + 1];

    // Find matching close tag (same partyId, after open tag)
    const matchingCloseTag = closeTags.find(
      (ct) =>
        ct.partyId === openTag.partyId &&
        ct.index > openTag.index &&
        (!nextOpenTag || ct.index < nextOpenTag.index),
    );

    const contentStart = openTag.index + openTag.fullMatch.length;

    if (matchingCloseTag) {
      // Complete party section
      const partyContent = cleanContent
        .slice(contentStart, matchingCloseTag.index)
        .trim();
      sections.push({
        type: 'party',
        partyId: openTag.partyId,
        content: partyContent,
        isStreaming: false,
      });

      // Check for content between this close tag and next open tag (or end)
      const afterCloseIndex =
        matchingCloseTag.index + matchingCloseTag.fullMatch.length;
      const nextSectionStart = nextOpenTag?.index ?? cleanContent.length;

      if (afterCloseIndex < nextSectionStart) {
        const betweenContent = cleanContent
          .slice(afterCloseIndex, nextSectionStart)
          .trim();
        if (betweenContent && !nextOpenTag) {
          // This is conclusion content (after last party section)
          sections.push({
            type: 'conclusion',
            content: betweenContent,
          });
        }
      }
    } else {
      // Unclosed party section (still streaming)
      const contentEnd = nextOpenTag?.index ?? cleanContent.length;
      const partyContent = cleanContent.slice(contentStart, contentEnd).trim();
      sections.push({
        type: 'party',
        partyId: openTag.partyId,
        content: partyContent,
        isStreaming: true,
      });
    }
  }

  return sections;
}

/**
 * Check if content has any party markers
 */
export function hasPartyMarkers(content: string): boolean {
  // Use non-global regex to avoid stateful lastIndex issues
  return PARTY_OPEN_TAG_TEST.test(content);
}

/**
 * Strip all party markers from content (for screen reader text)
 */
export function stripPartyMarkers(content: string): string {
  return content
    .replace(/\[PARTY:\w+\]/g, '')
    .replace(/\[\/PARTY:\w+\]/g, '')
    .trim();
}
