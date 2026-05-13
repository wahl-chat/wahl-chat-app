# Message Classifier Agent

## Purpose

Classifies user messages within an active exploration session to determine how to handle them. Distinguishes between follow-up questions, navigation commands, analysis requests, and summary requests.

## Responsibility

- Classify message intent within exploration context
- Detect navigation commands and their targets
- Extract questions for follow-up processing
- Identify special requests (analysis, summary)

## Input/Output

See `interface.py` for complete type definitions.

**Input:** `MessageClassifierInput`
- `message`: The user's message text
- `current_leaf_id`: ID of current subtopic (if any)
- `exploration_id`: ID of active exploration (if any)
- `has_exploration`: Whether an exploration is active

**Output:** `MessageClassifierOutput`
- `intent`: FOLLOWUP_QUESTION | NAVIGATION_COMMAND | ANALYSIS_REQUEST | SUMMARY_REQUEST
- `confidence`: 0.0-1.0 classification confidence
- `navigation_target`: NEXT | PREVIOUS | BACK | OVERVIEW (if navigation)
- `extracted_question`: The question text (if followup)
- `target_id`: Target topic/subtopic ID (if specified)

## Intent Handling

Based on `intent`:
- **FOLLOWUP_QUESTION**: Route to LeafConversationHandlerAgent
- **NAVIGATION_COMMAND**: Handle navigation in orchestrator
- **ANALYSIS_REQUEST**: Route to AnalyzerAgent
- **SUMMARY_REQUEST**: Route to SummaryGeneratorAgent

## Processing Logic (Stub)

Current stub uses keyword matching:
1. Check for navigation keywords -> NAVIGATION_COMMAND
2. Check for analysis keywords -> ANALYSIS_REQUEST
3. Check for summary keywords -> SUMMARY_REQUEST
4. Check for question patterns -> FOLLOWUP_QUESTION
5. Default to FOLLOWUP_QUESTION

## Future LLM Integration

See `prompts.py` for prompt templates. The LLM will:
1. Receive context about current exploration state
2. Understand message in conversation context
3. Classify with semantic understanding
4. Extract relevant entities (questions, targets)

## Error Handling

- No active exploration: May limit classification options
- LLM failure: Fall back to keyword matching

## Test Scenarios

1. **Navigation - Next**: "Weiter zum naechsten Thema"
   - Expected: NAVIGATION_COMMAND, navigation_target=NEXT

2. **Navigation - Back**: "Zurueck zur Uebersicht"
   - Expected: NAVIGATION_COMMAND, navigation_target=OVERVIEW

3. **Follow-up question**: "Wie unterscheiden sich SPD und CDU hier?"
   - Expected: FOLLOWUP_QUESTION, extracted_question set

4. **Analysis request**: "Kannst du das analysieren?"
   - Expected: ANALYSIS_REQUEST

5. **Summary request**: "Fass das zusammen"
   - Expected: SUMMARY_REQUEST
