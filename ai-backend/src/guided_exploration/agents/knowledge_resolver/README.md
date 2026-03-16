# Knowledge Resolver Agent

## Purpose

Resolves and structures knowledge for a specific subtopic from retrieved document chunks. Creates a cached knowledge representation used by content generation and conversation handling.

## Responsibility

- Process retrieved document chunks
- Extract summary points
- Structure party positions with citations
- Identify key facts and figures
- Build citation pool for content generation

## Input/Output

See `interface.py` for complete type definitions.

**Input:** `KnowledgeResolverInput`
- `subtopic_id`: ID of the subtopic to resolve
- `subtopic_name`: Display name
- `subtopic_description`: Description
- `parties`: List of party IDs to resolve
- `retrieved_chunks`: RAG-retrieved document chunks
- `context_id`: Election/political context

**Output:** `KnowledgeResolverOutput`
- `leaf_id`: The subtopic ID
- `summary_points`: Key points about the topic
- `party_positions`: Dict mapping party_id -> PartyPosition
- `key_facts`: Factual information extracted
- `citation_pool`: Available citations for content

## Data Flow

```
Retrieved Chunks
      │
      ▼
┌─────────────────┐
│ Knowledge       │
│ Resolver        │
└─────────────────┘
      │
      ▼
KnowledgeResolverOutput (cached)
      │
      ├──► ContentGeneratorAgent
      ├──► ConversationHandlerAgent
      └──► AnalyzerAgent
```

## Processing Logic (Stub)

Current stub generates mock data:
1. Generate template-based summary points
2. Create party positions from templates
3. Generate mock key facts
4. Build citation pool from parties

## Future LLM Integration

See `prompts.py` for prompt templates. The LLM will:
1. Analyze retrieved chunks for relevant content
2. Extract party positions with quotes
3. Identify factual information
4. Create proper citations with page numbers
5. Handle missing/conflicting information

## Citation Format

```python
Citation(
    id="spd-mietpreisbremse-1",
    party="spd",
    document="Wahlprogramm 2025",
    section="Bezahlbares Wohnen",
    page=34
)
```

## Error Handling

- No retrieved chunks: Return minimal stub data
- Missing party info: Skip that party's position
- Conflicting sources: Include both with notes
- LLM failure: Fall back to stub behavior

## Caching Strategy

Resolved knowledge should be cached per:
- `subtopic_id`
- `context_id`
- Chunk hash (for invalidation)

## Test Scenarios

1. **Full resolution**: All parties, multiple chunks
   - Expected: Complete positions for all parties, citations

2. **Partial data**: Some parties missing from chunks
   - Expected: Positions for available parties only

3. **Single party focus**: Query mentions only SPD
   - Expected: Detailed SPD position, others brief

4. **No chunks**: Empty retrieved_chunks
   - Expected: Minimal stub data, flag for missing info

5. **Conflicting sources**: Different info in chunks
   - Expected: Both viewpoints included with citations
