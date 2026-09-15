'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import {
  STUDY_DEV_TOOLS,
  clearDevCohortOverride,
} from '@/lib/pledge-study/dev-cohort-override';
import {
  type StudyCohort,
  isStudyContext,
} from '@/lib/pledge-study/study-config';

/**
 * Dev-only strip for driving the PledgeTracker study by hand: shows which arm
 * the current uid is in and flips it without clearing site data.
 *
 * The flip is local only (see dev-cohort-override.ts) — study_participants is
 * never written, so this cannot contaminate a real assignment. Reset drops the
 * override and reloads, restoring the hashed assignment.
 *
 * The other gate inputs are shown read-only on purpose: the cohort alone does
 * not decide what you see. With consent not accepted, or the kill switch off,
 * the experimental arm still renders nothing (gate.ts), and without this line
 * that reads as a broken toggle.
 */
function ChatStudyDevBar() {
  const contextId = useChatStore((state) => state.contextId);
  const studyEnabled = useChatStore((state) => state.studyEnabled);
  const studyConsent = useChatStore((state) => state.studyConsent);
  const studyCohort = useChatStore((state) => state.studyCohort);
  const setStudyCohortOverride = useChatStore(
    (state) => state.setStudyCohortOverride,
  );

  // Inlined at build time, so this whole component drops out of a prod bundle.
  if (!STUDY_DEV_TOOLS) {
    return null;
  }

  const cohortButton = (cohort: StudyCohort, label: string) => (
    <Button
      size="sm"
      variant={studyCohort === cohort ? 'default' : 'outline'}
      className="h-7 px-2 text-xs"
      onClick={() => setStudyCohortOverride(cohort)}
    >
      {label}
    </Button>
  );

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-dashed border-amber-500/50 bg-amber-500/5 px-3 py-1.5 md:px-4">
      <span className="text-xs font-semibold">PledgeTracker-Studie</span>
      <div className="flex items-center gap-1">
        {cohortButton('control', 'Kontrollgruppe')}
        {cohortButton('experimental', 'Manipulationsgruppe')}
      </div>
      <span className="text-xs text-muted-foreground">
        {isStudyContext(contextId) ? 'Studien-Kontext' : 'kein Studien-Kontext'}
        {' · '}
        {studyEnabled ? 'Killswitch an' : 'Killswitch aus'}
        {' · Einwilligung: '}
        {studyConsent ?? 'offen'}
        {' · Gruppe: '}
        {studyCohort ?? 'keine'}
      </span>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs"
        onClick={() => {
          clearDevCohortOverride();
          window.location.reload();
        }}
      >
        Reset
      </Button>
      <span className="ml-auto text-xs text-muted-foreground">
        Nur im Dev sichtbar
      </span>
    </div>
  );
}

export default ChatStudyDevBar;
