# Content Generator Agent

## Purpose

Generates the structured 4-section content for a subtopic with streaming support. This is the primary content shown when a user navigates to a subtopic.

## Responsibility

- Generate summary overview
- Create party position breakdowns
- List specific measures per party
- Stream content progressively for UI rendering
- Structure content with section markers

## Input/Output

See `interface.py` for complete type definitions.

**Input:** `ContentGeneratorInput`
- `subtopic_id`: ID of the subtopic
- `subtopic_name`: Display name
- `path`: Navigation path (e.g., ["wohnen", "mietpreisbremse"])
- `resolved_knowledge`: Pre-resolved knowledge from KnowledgeResolverAgent
- `context_id`: Election/political context
- `parties`: Parties to include in content

**Output:** `SubtopicContent` (from models.content)
- `subtopic_id`: The subtopic ID
- `path`: Navigation path
- `summary`: Overview text
- `party_positions`: List of PartyPosition objects
- `specific_measures`: List of SpecificMeasure objects
- `analysis`: None (generated separately on request)
- `citations`: All citations used

## Streaming Interface

```python
async for chunk in agent.stream(input):
    # chunk.section: "summary" | "party_positions" | "measures"
    # chunk.content: Text fragment
    # chunk.is_final: True for last chunk
```

## Content Structure

```
┌─────────────────────────────────┐
│ Summary (2-3 sentences)         │
├─────────────────────────────────┤
│ Party Positions                 │
│ ├── SPD: stance + details       │
│ ├── CDU: stance + details       │
│ └── ...                         │
├─────────────────────────────────┤
│ Specific Measures               │
│ ├── SPD: concrete proposal      │
│ ├── CDU: concrete proposal      │
│ └── ...                         │
└─────────────────────────────────┘
```

## Processing Logic (Stub)

Current stub generates content from resolved knowledge:
1. Create summary from summary_points
2. Convert party_positions dict to list
3. Generate mock specific measures
4. Stream in word chunks with section markers

## Future LLM Integration

See `prompts.py` for prompt templates. The LLM will:
1. Receive resolved knowledge as context
2. Generate flowing, readable summary
3. Phrase party positions neutrally
4. Extract concrete measures from sources
5. Stream tokens with section markers

## Streaming Configuration

- `WORDS_PER_CHUNK`: 5 words per stream chunk
- `CHUNK_DELAY`: 50ms between chunks
- Section markers: Used by UI to route content

## Error Handling

- Missing party position: Skip that party
- Empty resolved knowledge: Return minimal content
- Streaming error: Send error chunk, then final

## Test Scenarios

1. **Full content**: All parties, complete knowledge
   - Expected: All sections populated, proper streaming

2. **Partial parties**: Only SPD and CDU requested
   - Expected: Only those parties in positions/measures

3. **Missing knowledge**: Sparse resolved_knowledge
   - Expected: Minimal content, no errors

4. **Streaming test**: Verify chunk delivery
   - Expected: Proper section markers, final chunk

5. **Non-streaming execution**: Call execute() directly
   - Expected: Complete SubtopicContent returned
