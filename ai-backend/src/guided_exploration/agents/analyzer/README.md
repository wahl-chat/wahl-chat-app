# Analyzer Agent

## Purpose

Generates critical analysis for a subtopic on user request. Provides context, feasibility assessment, and considerations beyond the basic party positions.

## Responsibility

- Generate analytical summary
- Provide historical/current context
- Assess feasibility of proposals
- List additional considerations
- Cite external sources
- Stream analysis progressively

## Input/Output

See `interface.py` for complete type definitions.

**Input:** `AnalyzerInput`
- `leaf_id`: ID of the subtopic to analyze
- `subtopic_content`: Current subtopic content
- `resolved_knowledge`: Pre-resolved knowledge
- `context_id`: Election/political context
- `focus_areas`: Optional specific areas to focus on

**Output:** `Analysis` (from models.content)
- `summary`: Overall analytical assessment
- `context`: Background and current situation
- `feasibility`: List of feasibility considerations
- `considerations`: Additional points to consider
- `sources`: External sources used

## Streaming Interface

```python
async for chunk in agent.stream(input):
    # chunk.section: "summary" | "context" | "feasibility"
    # chunk.content: Text fragment
    # chunk.is_final: True for last chunk
```

## Analysis Structure

```
┌─────────────────────────────────┐
│ Summary (2-3 sentences)         │
│ Overall analytical assessment   │
├─────────────────────────────────┤
│ Context                         │
│ Historical background           │
│ Current situation               │
│ Relevant developments           │
├─────────────────────────────────┤
│ Feasibility                     │
│ • Legal aspects                 │
│ • Financial feasibility         │
│ • Political feasibility         │
│ • Implementation challenges     │
├─────────────────────────────────┤
│ Considerations                  │
│ • Long-term effects             │
│ • Unintended consequences       │
│ • International perspective     │
├─────────────────────────────────┤
│ Sources                         │
│ External references used        │
└─────────────────────────────────┘
```

## Processing Logic (Stub)

Current stub generates template-based analysis:
1. Create summary highlighting left-right divide
2. Generate generic context paragraph
3. List standard feasibility considerations
4. Add common considerations
5. Include placeholder sources

## Future LLM Integration

See `prompts.py` for prompt templates. The LLM will:
1. Analyze party positions for patterns
2. Research historical context
3. Assess practical feasibility
4. Identify potential issues
5. Reference credible sources

## Neutrality Requirements

Analysis must remain neutral:
- Present facts, not opinions
- Acknowledge uncertainty
- Show multiple perspectives
- Avoid value judgments
- Let users draw conclusions

## Error Handling

- Missing content: Generate minimal analysis
- Focus areas not covered: Acknowledge gaps
- Sources unavailable: Note limitation
- Streaming error: Send partial + error flag

## Test Scenarios

1. **Full analysis**: Complete subtopic content
   - Expected: All sections populated, balanced

2. **Focused analysis**: Specific focus_areas provided
   - Expected: Analysis emphasizes those areas

3. **Controversial topic**: Highly debated issue
   - Expected: Extra care in neutrality

4. **Technical topic**: Complex policy details
   - Expected: Clear feasibility breakdown

5. **Streaming test**: Verify section delivery
   - Expected: Proper markers, smooth flow

6. **Non-streaming**: Call execute() directly
   - Expected: Complete Analysis object
