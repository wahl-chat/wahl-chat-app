/**
 * Exploration Study Module
 *
 * A standalone study frontend with separate pages from wahl.chat, featuring:
 * - Full-screen exploration views during task pages
 * - Progress header for participants
 * - State machine-based navigation
 */

// Types
export * from './types';

// Utils
export * from './utils';

// Hooks
export * from './hooks';

// Services
export { studyApi } from './services/study-api';
export {
  getTelemetry,
  type TelemetryEventInput,
  type TelemetryEventType,
} from './services/telemetry';

// Data
export * from './data/fake-parties';

// Components
export * from './components';
