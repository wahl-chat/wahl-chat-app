# Query Classifier Agent

## Purpose

Classifies incoming user queries to determine the appropriate routing strategy. This is the entry point for all new queries to the guided exploration system.

## Responsibility

- Analyze user query text to determine intent
- Detect mentioned political parties
- Detect relevant topics
- Assess whether clarification is needed
- Return classification with confidence score

## Input/Output

See `interface.py` for complete type definitions.

**Input:** `QueryClassifierInput`
- `query`: The user's raw query text
- `context_id`: Election/political context (e.g., "btw2025")
- `conversation_history`: Optional previous messages for context

**Output:** `QueryClassifierOutput`
- `query_type`: FACTUAL | EXPLORATORY | CLARIFICATION
- `confidence`: 0.0-1.0 classification confidence
- `detected_parties`: List of party IDs found in query
- `detected_topics`: List of topic IDs found in query
- `needs_clarification`: Whether to ask for clarification
- `clarification_question`: Question to ask if clarification needed

## Routing Strategy

Based on `query_type`:
- **FACTUAL**: Route to direct answer generation (questions about specific positions or comparisons)
- **EXPLORATORY**: Route to full exploration flow (planning -> tree)
- **CLARIFICATION**: Ask clarification question first

## Processing Logic

Uses LLM to classify queries:
1. Check for concrete position questions or comparisons -> FACTUAL
2. Check for unclear patterns -> CLARIFICATION
3. Complex topics requiring deeper exploration -> EXPLORATORY

## Future LLM Integration

See `prompts.py` for prompt templates. The LLM will:
1. Receive system prompt explaining classification task
2. Analyze query with semantic understanding
3. Return structured classification output
4. Provide reasoning for the classification

## Error Handling

- Invalid input: Raise `AgentValidationError`
- LLM failure: Raise `AgentExecutionError` with cause
- Low confidence: Consider returning CLARIFICATION

## Test Scenarios

1. **Factual query**: "Was ist die Position der SPD zum Mindestlohn?"
   - Expected: FACTUAL, parties=["spd"]

2. **Factual comparison**: "Vergleich SPD und CDU zur Mietpreisbremse"
   - Expected: FACTUAL, parties=["spd", "cdu"]

3. **Exploratory query**: "Was sagen die Parteien zur Wohnungspolitik?"
   - Expected: EXPLORATORY

4. **Ambiguous query**: "Politik"
   - Expected: CLARIFICATION, needs_clarification=True

5. **Broad topic query**: "Was will die SPD?"
   - Expected: EXPLORATORY, parties=["spd"]
