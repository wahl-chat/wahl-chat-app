"""State machine for exploration study sessions."""

from enum import Enum


class StudyState(str, Enum):
    """
    States for a participant's progression through the study.

    Each state represents the CURRENT step the participant should see/complete.

    Flow:
    CONSENT -> DEMOGRAPHICS -> LITERACY -> TUTORIAL
      -> TASK_1 -> QUESTIONNAIRE_1 -> RECALL_1 -> QUIZ_1
      -> TASK_2 -> QUESTIONNAIRE_2 -> RECALL_2 -> QUIZ_2
      -> PREFERENCES -> COMPLETE
    """

    # Onboarding steps
    CONSENT = "consent"
    DEMOGRAPHICS = "demographics"
    LITERACY = "literacy"
    TUTORIAL = "tutorial"

    # Task 1 (first condition)
    TASK_1 = "task_1"
    QUESTIONNAIRE_1 = "questionnaire_1"
    RECALL_1 = "recall_1"
    QUIZ_1 = "quiz_1"

    # Task 2 (second condition)
    TASK_2 = "task_2"
    QUESTIONNAIRE_2 = "questionnaire_2"
    RECALL_2 = "recall_2"
    QUIZ_2 = "quiz_2"

    # Final states
    PREFERENCES = "preferences"
    COMPLETE = "complete"

    # Error/abandoned states
    ABANDONED = "abandoned"


# Valid state transitions (from current step -> next step after completion)
TRANSITIONS: dict[StudyState, list[StudyState]] = {
    # Onboarding flow
    StudyState.CONSENT: [StudyState.DEMOGRAPHICS],
    StudyState.DEMOGRAPHICS: [StudyState.LITERACY],
    StudyState.LITERACY: [StudyState.TUTORIAL],
    StudyState.TUTORIAL: [StudyState.TASK_1],
    # Task 1 flow
    StudyState.TASK_1: [StudyState.QUESTIONNAIRE_1],
    StudyState.QUESTIONNAIRE_1: [StudyState.RECALL_1],
    StudyState.RECALL_1: [StudyState.QUIZ_1],
    StudyState.QUIZ_1: [StudyState.TASK_2],
    # Task 2 flow
    StudyState.TASK_2: [StudyState.QUESTIONNAIRE_2],
    StudyState.QUESTIONNAIRE_2: [StudyState.RECALL_2],
    StudyState.RECALL_2: [StudyState.QUIZ_2],
    StudyState.QUIZ_2: [StudyState.PREFERENCES],
    # Final
    StudyState.PREFERENCES: [StudyState.COMPLETE],
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


def get_task_number(state: StudyState) -> int | None:
    """Get the task number (1 or 2) for task-related states, or None."""
    task_1_states = {
        StudyState.TASK_1,
        StudyState.QUESTIONNAIRE_1,
        StudyState.RECALL_1,
        StudyState.QUIZ_1,
    }
    task_2_states = {
        StudyState.TASK_2,
        StudyState.QUESTIONNAIRE_2,
        StudyState.RECALL_2,
        StudyState.QUIZ_2,
    }
    if state in task_1_states:
        return 1
    if state in task_2_states:
        return 2
    return None
