# Summary Generator Agent

## Purpose

Generates summaries for different contexts: leaf conversations, quick overviews, and final exploration summaries. Uses discriminated union input to handle all summary types.

## Responsibility

- Generate leaf conversation summaries
- Generate quick summaries without exploration
- Generate final exploration summaries
- Adapt format to summary type

## Input/Output

See `interface.py` for complete type definitions.

**Input Types (Discriminated Union):**

1. `LeafSummaryInput` (summary_type="leaf")
   - `leaf_id`: Subtopic ID
   - `conversation`: The conversation to summarize
   - `subtopic_content`: Content discussed

2. `QuickSummaryInput` (summary_type="quick")
   - `query`: Original user query
   - `retrieved_chunks`: RAG results
   - `detected_parties`: Parties in query
   - `context_id`: Political context

3. `FinalSummaryInput` (summary_type="final")
   - `exploration_id`: Exploration ID
   - `original_query`: Starting query
   - `summary_tree`: Tree of leaf summaries
   - `explored_subtopics`: List of explored IDs

**Output Types:**

1. `LeafSummary` - For leaf conversations
2. `QuickSummaryOutput` - For quick summaries
3. `FinalSummary` - For exploration completion

## Summary Types

### Leaf Summary
Generated when user leaves a subtopic or requests summary.
```
┌─────────────────────────────────┐
│ Overview (2-3 sentences)        │
│ Key Points (3-5 bullets)        │
│ Party Comparison (1 paragraph)  │
└─────────────────────────────────┘
```

### Quick Summary
Generated for users who choose "quick summary" over exploration.
```
┌─────────────────────────────────┐
│ Overview                        │
│ Topic Highlights                │
│ Major Differences               │
│ Major Agreements                │
└─────────────────────────────────┘
```

### Final Summary
Generated when user ends exploration.
```
┌─────────────────────────────────┐
│ Closing Summary                 │
│ Overall Overview                │
│ Key Findings (bullets)          │
└─────────────────────────────────┘
```

## Processing Logic (Stub)

Current stub uses templates:
1. Detect input type via isinstance()
2. Route to appropriate generator method
3. Generate template-based content
4. Return typed output

## Future LLM Integration

See `prompts.py` for prompt templates. The LLM will:
1. Analyze input content thoroughly
2. Extract key insights
3. Generate concise summaries
4. Highlight important findings
5. Maintain consistency across types

## Usage Pattern

```python
# Leaf summary
output = await agent.execute(LeafSummaryInput(
    summary_type="leaf",
    leaf_id="wohnen.mietpreisbremse",
    conversation=conversation,
    subtopic_content=content
))
# Returns LeafSummary

# Quick summary
output = await agent.execute(QuickSummaryInput(
    summary_type="quick",
    query="Mietpreisbremse",
    ...
))
# Returns QuickSummaryOutput
```

## Error Handling

- Unknown summary type: Raise ValueError
- Empty conversation: Generate minimal summary
- No explored subtopics: Note in final summary
- Missing data: Graceful degradation

## Test Scenarios

1. **Leaf summary - full conversation**
   - Expected: Comprehensive summary with key points

2. **Leaf summary - minimal conversation**
   - Expected: Brief summary noting limited discussion

3. **Quick summary - broad query**
   - Expected: Wide-ranging highlights

4. **Quick summary - specific query**
   - Expected: Focused on detected topics/parties

5. **Final summary - many topics explored**
   - Expected: Rich findings, comprehensive closing

6. **Final summary - no topics explored**
   - Expected: Graceful message about unexplored content

7. **Type discrimination**: Verify correct routing
   - Expected: Each type returns correct output type
