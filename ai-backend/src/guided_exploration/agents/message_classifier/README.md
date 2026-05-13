# Message Classifier Agent

## Purpose

Classifies user messages within an active exploration session to determine how to handle them. Distinguishes between follow-up questions and navigation commands.

## Responsibility

- Classify message intent within exploration context
- Detect navigation commands and their targets
- Extract questions for follow-up processing

## Input/Output

See `interface.py` for complete type definitions.

**Input:** `MessageClassifierInput`
- `message`: The user's message text
- `context_name`: Human-readable context name (e.g. "Bundestagswahl 2025")
- `current_leaf_id`: ID of current subtopic (if any)
- `exploration_id`: ID of active exploration (if any)
- `conversation_history`: Previous messages for back-reference resolution
- `last_assistant_message`: Full untruncated last assistant turn

**Output:** `MessageClassifierOutput`
- `intent`: FOLLOWUP_QUESTION | NAVIGATION_COMMAND
- `confidence`: 0.0-1.0 classification confidence
- `navigation_target`: NEXT | PREVIOUS | BACK | OVERVIEW (if navigation)
- `extracted_question`: The question text (if followup)
- `target_id`: Target topic/subtopic ID (if specified)

## Intent Handling

Based on `intent`:
- **FOLLOWUP_QUESTION**: Route to LeafConversationHandlerAgent
- **NAVIGATION_COMMAND**: Handle navigation in orchestrator

Analysis is triggered explicitly via a dedicated UI action that calls `AnalysisHandler.request_analysis` — it does not flow through this classifier.

## Test Scenarios

1. **Navigation - Next**: "Weiter zum nächsten Thema"
   - Expected: NAVIGATION_COMMAND, navigation_target=NEXT

2. **Navigation - Back**: "Zurück zur Übersicht"
   - Expected: NAVIGATION_COMMAND, navigation_target=OVERVIEW

3. **Follow-up question**: "Wie unterscheiden sich SPD und CDU hier?"
   - Expected: FOLLOWUP_QUESTION, extracted_question set

4. **Short affirmation after a clarifying question**: "gerne"
   - Expected: FOLLOWUP_QUESTION, extracted_question reconstructed from the last assistant turn
