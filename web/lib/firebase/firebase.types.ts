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
  /** Only participants have an arm. */
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
