import { describe, expect, test } from 'bun:test';
import { opensWithLabel, pointAnchorId, splitSummary } from './chat-summary';

const ANSWER = `**Kurz gesagt:**
- **CDU/CSU**: dafür, weil die Rente stabil bleiben soll
- **Grüne**: dagegen, zu teuer

**CDU/CSU** stimmte dafür [0].

**Grüne** stimmten dagegen [1].`;

describe('splitSummary', () => {
  test('splits the block off and keeps the body', () => {
    const { summary, body } = splitSummary(ANSWER);
    expect(summary).toEqual([
      { label: 'CDU/CSU', text: 'dafür, weil die Rente stabil bleiben soll' },
      { label: 'Grüne', text: 'dagegen, zu teuer' },
    ]);
    expect(body.trimStart().startsWith('**CDU/CSU** stimmte')).toBe(true);
  });

  test('a point drops references and bold the model left in', () => {
    const { summary } = splitSummary(
      '**Kurz gesagt:**\n- **EUNAVFOR MED**: bis **November 2027** verlängert [0].\n- **SEA GUARDIAN**: fortgeführt [1, 2]\n\nText.',
    );
    expect(summary).toEqual([
      { label: 'EUNAVFOR MED', text: 'bis November 2027 verlängert.' },
      { label: 'SEA GUARDIAN', text: 'fortgeführt' },
    ]);
  });

  test('an answer without the block is all body', () => {
    expect(splitSummary('Kurze Antwort [0].')).toEqual({
      summary: null,
      body: 'Kurze Antwort [0].',
    });
  });

  test('a stream inside the heading shows nothing yet', () => {
    expect(splitSummary('**Kurz ge')).toEqual({ summary: [], body: '' });
  });

  test('a stream inside the list shows the points so far', () => {
    const { summary, body } = splitSummary(
      '**Kurz gesagt:**\n- **SPD**: dafür\n- **Gr',
    );
    expect(summary).toEqual([{ label: 'SPD', text: 'dafür' }]);
    expect(body).toBe('');
  });
});

describe('splitSummary edge cases', () => {
  test('a block with an unlabelled line stays in the text', () => {
    const text =
      '**Kurz gesagt:**\n- **SPD**: dafür\n- Grüne: dagegen\n\nMehr.';
    expect(splitSummary(text)).toEqual({ summary: null, body: text });
  });

  test('a bold paragraph right after the list is not swallowed', () => {
    const { summary, body } = splitSummary(
      '**Kurz gesagt:**\n- **SPD**: dafür\n**SPD**: Die Fraktion stimmte zu.',
    );
    expect(summary).toEqual([{ label: 'SPD', text: 'dafür' }]);
    expect(body).toBe('**SPD**: Die Fraktion stimmte zu.');
  });

  test('a colon inside the bold is not part of the label', () => {
    expect(
      splitSummary('**Kurz gesagt:**\n- **Grüne:** dagegen\n').summary,
    ).toEqual([{ label: 'Grüne', text: 'dagegen' }]);
  });

  test('a blank line after the heading is fine', () => {
    expect(
      splitSummary('**Kurz gesagt:**\n\n- **AfD**: dagegen\n').summary,
    ).toEqual([{ label: 'AfD', text: 'dagegen' }]);
  });
});

describe('opensWithLabel', () => {
  test('only a block that opens with the label counts', () => {
    expect(
      opensWithLabel('Text.\n\n**CDU/CSU**: Die Fraktion …', 'CDU/CSU'),
    ).toBe(true);
    expect(opensWithLabel('**Grüne:** dagegen', 'Grüne')).toBe(true);
    expect(opensWithLabel('Die **SPD** stimmte zu.', 'SPD')).toBe(false);
  });
});

describe('pointAnchorId', () => {
  test('makes labels safe ids', () => {
    expect(pointAnchorId('m1', 'CDU/CSU')).toBe('m1-cdu-csu');
    expect(pointAnchorId('m1', 'BÜNDNIS 90/DIE GRÜNEN')).toBe(
      'm1-bundnis-90-die-grunen',
    );
  });
});
