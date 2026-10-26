import type { Topic } from '@/components/topics/topics.data';
import type {
  StudyAssignmentSource,
  StudyCohort,
  StudyConsentAnswer,
  StudyConsentStage,
  StudyDeclineReason,
  StudyParticipation,
} from '@/lib/pledge-study/types';
import type { ProlificMetadata } from '@/lib/prolific-study/prolific-metadata';
import type { GroupedMessage } from '@/lib/stores/chat-store.types';
import type { WahlSwiperResultHistory } from '@/lib/wahl-swiper/wahl-swiper.types';
import type { Timestamp } from 'firebase/firestore';

export type ChatSession = {
  id: string;
  user_id: string;
  /** PledgeTracker study: cohort stamp for joining chat data to the study. */
  study_cohort?: StudyCohort;
  is_pledge_study?: boolean;
  party_id?: string;
  is_public?: boolean;
  title?: string;
  created_at?: Date;
  updated_at?: Date;
  party_ids?: string[];
  sharing_snapshot?: {
    id: string;
    messages_length_at_sharing: number;
  };
  tenant_id?: string;
  context_id?: string;
  visit_id?: string;
};

export type PageVisit = {
  id: string;
  user_id: string;
  started_at: Date;
  last_seen_at: Date;
  visible_ms: number;
  landing_path?: string;
  last_path?: string;
  context_id?: string;
  tenant_id?: string;
  chat_session_ids?: string[];
  embedded?: boolean;
};

export type Context = {
  context_id: string;
  name: string;
  icon_url: string;
  type: 'election' | 'general';
  // Stored as a Firestore timestamp and mapped through firestoreTimestampToDate()
  // in firebase-server.ts, so this is a Date once it reaches any consumer.
  date: Date | null;
  location_name: string;
  is_active: boolean;
  supports_swiper: boolean;
  supports_voting_behavior: boolean;
};

export type ShareableChatSessionSnapshot = {
  id: string;
  session_id: string;
  title: string;
  shared_by: string;
  party_ids: string[];
  messages: GroupedMessage[];
  shared_at: Date;
  context_id?: string;
};

export type ProposedQuestion = {
  id: string;
  content: string;
  topic: string;
  location: 'banner' | 'chat' | 'home';
  partyId: string;
};

export type SourceDocument = {
  id: string;
  storage_url: string;
  name: string;
  publish_date?: Date;
  party_id: string;
};

export type Tenant = {
  id: string;
  name: string;
};

export type ExampleQuestionShareableChatSession = {
  id: string;
  question: string;
  topic: Topic;
};

export type LlmSystemStatus = {
  is_at_rate_limit: boolean;
};

/** Kill switch for the PledgeTracker study (system_status/pledge_study). */
export type StudyStatus = {
  enabled: boolean;
};

/** One interaction-log entry on a study participant (timestamped by client). */
export type StudyParticipantEvent = {
  type: string;
  trigger?: string;
  at: Timestamp;
};

/**
 * study_participants/{uid} — consent-gated per-participant record for the
 * PledgeTracker study. Counts and firsts are DERIVED from `events` at
 * analysis time (min/count per type), so the doc stays append-mostly.
 */
export type StudyParticipant = {
  consent_answer: StudyConsentAnswer;
  consent_at: Timestamp;
  /**
   * Which of the two consent screens the answer came from. Acceptances are
   * always 'consent'; declines split into "refused the short ask" and "read
   * the Einverständniserklärung, then refused", which is the whole point of
   * recording it. Absent means a pre-2026-09-17 record, written when both
   * screens shared one undifferentiated decline.
   */
  consent_stage?: StudyConsentStage;
  /** Only on declines: a "Nein" button ('explicit') vs a dismissal. */
  decline_reason?: StudyDeclineReason;
  /** Derived from consent_answer; stored so queries need not infer it. */
  participation?: StudyParticipation;
  /**
   * Set for BOTH answers: a decline is still assigned an arm, so the
   * comparison is not limited to the few who consent. Absent only on rows
   * written before 2026-09-18, when declines carried no arm.
   */
  cohort?: StudyCohort;
  /**
   * 'override' marks a row whose arm was forced by a ?sg= link. EXCLUDE these
   * from analysis: they are testers, not participants, and counting them would
   * skew the 50:50 split. Absent means 'hash'.
   */
  assignment_source?: StudyAssignmentSource;
  /** Which ?sg= variant forced this row, when assignment_source is 'override'. */
  override_variant?: string;
  override_at?: Timestamp;
  /** Election context the consent was answered in — set on accept AND decline. */
  context_id?: string;
  /**
   * Parties selected when the consent was answered, sorted. Recorded for both
   * answers so refusal can be modelled against party choice (the hypothesis:
   * users who came to chat with one specific party opt in less often). `[]`
   * means no party was selected yet; absent means a pre-2026-09 record.
   */
  party_ids?: string[];
  questionnaire_clicked_at?: Timestamp;
  events?: StudyParticipantEvent[];
};

export type FirebaseWahlSwiperResult = {
  id: string;
  user_id: string;
  created_at: Date;
  history: WahlSwiperResultHistory;
  is_prolific_study?: boolean;
  prolific_metadata?: ProlificMetadata;
};

/** The feed's view of one parliament's sitting day. Built on the client from
 * `FeedEdition` + `FeedItem`s (see `lib/daily/editions.ts`) in the reader's
 * language, or read as-is from a local preview file. */
export type DigestParliamentId = 'bundestag' | 'landtag_st' | 'landtag_bw';

export type DigestVoteParty = {
  party_id: string;
  name: string;
  color: string;
  yes: number;
  no: number;
  abstain: number;
  no_show: number;
};

export type DigestVote = {
  poll_id: number;
  title: string;
  short_title: string;
  summary: string | null;
  /** The source's own account of the motion; absent on older digests. */
  description?: string | null;
  topics: string[];
  outcome: 'angenommen' | 'abgelehnt' | null;
  citation_url: string | null;
  parties: DigestVoteParty[];
  /** Absent on digests built before the feed's chat handoff. */
  suggested_questions?: string[];
  /** The `FeedItem` it came from; absent on local previews. */
  item_id?: string;
  legacy_keys?: string[];
};

export type DigestCitation = {
  title: string;
  url: string;
  /** Set on speech citations; absent on older digests. */
  speaker?: string | null;
  party_id?: string | null;
  party_name?: string | null;
  color?: string | null;
  /** The speech's own video file, when one exists. */
  video_url?: string | null;
};

export type DigestSpeaker = {
  name: string;
  /** The speech in the Plenarprotokoll PDF, at its page when known. */
  url: string | null;
  /** The speech's own video, and a link to it; absent on older digests. */
  video_url?: string | null;
  video_link?: string | null;
};

export type DigestPartyPosition = {
  party_id: string;
  party_name: string;
  color: string;
  speakers: DigestSpeaker[];
  position: string;
};

export type DigestAudioSummary = {
  title: string;
  url: string;
  /** Lets the player show the length before the file's metadata loads. */
  duration_seconds?: number | null;
};

export type DigestQuote = {
  text: string;
  speaker: string;
  party_id: string;
  party_name: string;
};

export type DigestSessionSection = {
  /** The primary topic; `topics` holds it plus an optional second one. */
  topic: string;
  /** Absent on local previews and digests built with one topic only. */
  topics?: string[];
  headline: string;
  summary: string;
  /** One entry per Fraktion that spoke; absent on older digests. */
  positions?: DigestPartyPosition[];
  agenda_items: string[];
  citations: DigestCitation[];
  video_url: string | null;
  /** A spoken summary of the section; the digest builder does not write one. */
  audio?: DigestAudioSummary | null;
  /** Fields below are absent on older digests. Exactly three bullets. */
  key_points?: string[];
  /** 1–5, relative to the other sections of the same sitting only. */
  heat?: number | null;
  /** Estimated from the speeches' word count. */
  debate_minutes?: number | null;
  opening_quote?: DigestQuote | null;
  /** Fraktion of the debate's first speaker. */
  opened_by?: string | null;
  suggested_questions?: string[];
  /** The `FeedItem` it came from; absent on local previews. */
  item_id?: string;
  legacy_keys?: string[];
};

export type DigestSession = {
  protocols: { protocol_id: string; pdf_url: string | null }[];
  sections: DigestSessionSection[];
  other_topics: string[];
};

export type DailyDigest = {
  id: string;
  parliament: DigestParliamentId;
  parliament_name: string;
  region: string;
  /** ISO day, `YYYY-MM-DD`. */
  date: string;
  votes: DigestVote[];
  session: DigestSession | null;
};

// Firestore `feed_editions/{edition_id}` and `feed_items/{item_id}`, written
// by the backend feed builder (`ai-backend/src/feed/models.py`).

export type FeedLocale = 'de' | 'en';

export type LocalizedPosition = { party_id: string; text: string };

export type LocalizedContent = {
  headline: string;
  teaser: string | null;
  key_points: string[];
  positions: LocalizedPosition[];
  suggested_questions: string[];
  /** Other locales only: the verbatim German quote stays in `debate`. */
  quote_translation: string | null;
  origin: 'generated' | 'translated';
};

export type DebateFacts = {
  protocols: { protocol_id: string; pdf_url: string | null }[];
  agenda_items: string[];
  citations: DigestCitation[];
  /** Same order as `positions` in every locale's content. */
  parties: {
    party_id: string;
    party_name: string;
    color: string;
    speakers: DigestSpeaker[];
  }[];
  video_url: string | null;
  heat: number | null;
  debate_minutes: number | null;
  opened_by: string | null;
  opening_quote: DigestQuote | null;
};

export type VoteFacts = {
  poll_id: number;
  official_title: string;
  outcome: 'angenommen' | 'abgelehnt' | null;
  citation_url: string | null;
  description: string | null;
  parties: DigestVoteParty[];
};

export type FeedItem = {
  id: string;
  kind: 'debate' | 'vote';
  edition_id: string;
  parliament: DigestParliamentId;
  parliament_name: string;
  region: string;
  /** ISO day, `YYYY-MM-DD`. */
  date: string;
  rank: number;
  topics: string[];
  status: 'published' | 'retracted';
  debate: DebateFacts | null;
  vote: VoteFacts | null;
  /** German always; other locales once translated. */
  content: { de: LocalizedContent } & Partial<
    Record<FeedLocale, LocalizedContent>
  >;
  legacy_keys: string[];
};

export type FeedEdition = {
  id: string;
  parliament: DigestParliamentId;
  parliament_name: string;
  region: string;
  /** ISO day, `YYYY-MM-DD`. */
  date: string;
  protocols: { protocol_id: string; pdf_url: string | null }[];
  item_ids: string[];
  other_topics: string[];
};

/** One parliament's recent editions and their items. */
export type ParliamentFeed = { editions: FeedEdition[]; items: FeedItem[] };
