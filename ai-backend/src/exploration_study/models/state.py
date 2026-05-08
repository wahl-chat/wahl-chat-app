"""State machine for exploration study sessions."""

from enum import Enum


class StudyState(str, Enum):
    """
    States for a participant's progression through the study.

    Each state represents the CURRENT step the participant should see/complete.

    Between-subjects A/B design: each participant sees only one condition.

    Flow:
    CONSENT -> TUTORIAL -> TASK -> QUESTIONNAIRE -> QUIZ
      -> DEMOGRAPHICS -> COMPLETE

    All non-consent survey material is asked *after* the task so
    participants stay fresh for the exploration and knowledge quiz.
    """

    # Onboarding steps
    CONSENT = "consent"
    DEMOGRAPHICS = "demographics"
    TUTORIAL = "tutorial"

    # Task (single condition)
    TASK = "task"
    QUESTIONNAIRE = "questionnaire"
    QUIZ = "quiz"

    # Final states
    COMPLETE = "complete"

    # Error/abandoned states
    ABANDONED = "abandoned"


# Valid state transitions (from current step -> next step after completion)
TRANSITIONS: dict[StudyState, list[StudyState]] = {
    # Onboarding flow (minimal — straight to the task to keep focus fresh)
    StudyState.CONSENT: [StudyState.TUTORIAL],
    StudyState.TUTORIAL: [StudyState.TASK],
    # Task flow
    StudyState.TASK: [StudyState.QUESTIONNAIRE],
    StudyState.QUESTIONNAIRE: [StudyState.QUIZ],
    StudyState.QUIZ: [StudyState.DEMOGRAPHICS],
    # Post-task survey material — demographics is the final survey step
    StudyState.DEMOGRAPHICS: [StudyState.COMPLETE],
    # Final
    StudyState.COMPLETE: [],
    # Abandoned can be reached from any state
    StudyState.ABANDONED: [],
}


def can_transition(from_state: StudyState, to_state: StudyState) -> bool:
    """Check if a state transition is valid."""
    # Special case: any state can transition to ABANDONED
    if to_state == StudyState.ABANDONED:
        return from_state != StudyState.COMPLETE
    return to_state in TRANSITIONS.get(from_state, [])


def get_next_state(current_state: StudyState) -> StudyState | None:
    """Get the next state in the normal progression, or None if at end."""
    allowed = TRANSITIONS.get(current_state, [])
    # Filter out ABANDONED from allowed transitions for normal progression
    normal = [s for s in allowed if s != StudyState.ABANDONED]
    return normal[0] if normal else None
