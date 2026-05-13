# Leaf Conversation Handler Agent

## Purpose

Handles follow-up questions within a leaf conversation. Uses resolved knowledge and conversation history to generate contextual, grounded responses.

## Responsibility

- Process follow-up questions in context
- Generate relevant, cited responses
- Maintain conversation coherence
- Suggest follow-up questions
- Stream responses progressively

## Input/Output

See `interface.py` for complete type definitions.

**Input:** `LeafConversationHandlerInput`
- `message`: The user's follow-up message
- `leaf_id`: Current subtopic ID
- `conversation_history`: Previous messages in conversation
- `resolved_knowledge`: Pre-resolved knowledge for context
- `context_id`: Election/political context

**Output:** `ConversationHandlerOutput`
- `response`: The generated response text
- `citations`: Citations supporting the response
- `suggested_followups`: 1-2 suggested follow-up questions

## Streaming Interface

```python
async for chunk in agent.stream(input):
    # chunk.section: "response"
    # chunk.content: Text fragment
    # chunk.is_final: True for last chunk
```

## Conversation Flow

```
User: "Wie unterscheiden sich SPD und CDU hier?"
          │
          ▼
┌──────────────────────────────┐
│ LeafConversationHandlerAgent     │
│ ├── Context: resolved_knowledge
│ ├── History: previous messages
│ └── Question analysis         │
└──────────────────────────────┘
          │
          ▼
Streamed response with citations
          │
          ▼
Suggested follow-ups
```

## Processing Logic (Stub)

Current stub generates responses based on patterns:
1. Check for party mentions -> Focus on those parties
2. Check for comparison patterns -> Generate comparison
3. Check for why/reason patterns -> Explain reasoning
4. Default -> General response with party overview

## Future LLM Integration

See `prompts.py` for prompt templates. The LLM will:
1. Receive full conversation context
2. Understand question intent
3. Use resolved knowledge for grounded answers
4. Cite sources appropriately
5. Generate natural follow-up suggestions

## Response Guidelines

- Stay within scope of resolved knowledge
- Always cite sources when making claims
- Acknowledge when information is limited
- Maintain neutral, factual tone
- Keep responses focused and concise

## Error Handling

- No relevant knowledge: Acknowledge gap, stay helpful
- Ambiguous question: Ask for clarification
- Off-topic question: Redirect to relevant content
- Streaming error: Send partial response + error

## Test Scenarios

1. **Party-specific question**: "Was sagt die SPD dazu?"
   - Expected: Focused SPD response with citations

2. **Comparison question**: "Unterschied SPD und CDU?"
   - Expected: Comparative response highlighting differences

3. **Why question**: "Warum gibt es diese Unterschiede?"
   - Expected: Explanatory response with reasoning

4. **Context continuation**: Follow-up on previous answer
   - Expected: Response building on history

5. **Off-topic question**: Question unrelated to subtopic
   - Expected: Polite redirection to topic

6. **Streaming test**: Verify progressive delivery
   - Expected: Proper chunks with response section
