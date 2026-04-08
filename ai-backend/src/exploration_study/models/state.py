"""State machine for exploration study sessions."""

from enum import Enum


class StudyState(str, Enum):
    """
    States for a participant's progression through the study.

    Each state represents the CURRENT step the participant should see/complete.

    Between-subjects A/B design: each participant sees only one condition.

    Flow:
    CONSENT -> DEMOGRAPHICS -> LITERACY -> TUTORIAL
      -> TASK -> QUESTIONNAIRE -> RECALL -> QUIZ -> COMPLETE
    """

    # Onboarding steps
    CONSENT = "consent"
    DEMOGRAPHICS = "demographics"
    LITERACY = "literacy"
    TUTORIAL = "tutorial"

    # Task (single condition)
    TASK = "task"
    QUESTIONNAIRE = "questionnaire"
    RECALL = "recall"
    QUIZ = "quiz"

    # Final states
    COMPLETE = "complete"

    # Error/abandoned states
    ABANDONED = "abandoned"


# Valid state transitions (from current step -> next step after completion)
TRANSITIONS: dict[StudyState, list[StudyState]] = {
    # Onboarding flow
    StudyState.CONSENT: [StudyState.DEMOGRAPHICS],
    StudyState.DEMOGRAPHICS: [StudyState.LITERACY],
    StudyState.LITERACY: [StudyState.TUTORIAL],
    StudyState.TUTORIAL: [StudyState.TASK],
    # Task flow
    StudyState.TASK: [StudyState.QUESTIONNAIRE],
    StudyState.QUESTIONNAIRE: [StudyState.RECALL],
    StudyState.RECALL: [StudyState.QUIZ],
    StudyState.QUIZ: [StudyState.COMPLETE],
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
