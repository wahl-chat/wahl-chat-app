import { afterEach, describe, expect, it } from 'bun:test';
import {
  STUDY_QUESTIONNAIRE_FORM_ID,
  assignCohort,
  questionnaireFormId,
} from './study-config';

const ENV_KEY = 'NEXT_PUBLIC_STUDY_QUESTIONNAIRE_URL';
const FORM_ID = 'aBcDeFgH1234';

function setUrl(value: string | undefined): void {
  if (value === undefined) {
    delete process.env[ENV_KEY];
    return;
  }
  process.env[ENV_KEY] = value;
}

afterEach(() => {
  setUrl(undefined);
});

describe('questionnaireFormId', () => {
  it('parses the id out of the link the research team provides', () => {
    setUrl(`https://forms.fillout.com/t/${FORM_ID}`);
    expect(questionnaireFormId()).toBe(FORM_ID);
  });

  it('ignores a trailing slash and any query string', () => {
    setUrl(`https://forms.fillout.com/t/${FORM_ID}/`);
    expect(questionnaireFormId()).toBe(FORM_ID);

    setUrl(
      `https://forms.fillout.com/t/${FORM_ID}?user_id=abc&chat_session_id=def`,
    );
    expect(questionnaireFormId()).toBe(FORM_ID);
  });

  it('accepts a bare form id', () => {
    setUrl(FORM_ID);
    expect(questionnaireFormId()).toBe(FORM_ID);
  });

  it('tolerates surrounding whitespace from a copy-paste', () => {
    setUrl(`  https://forms.fillout.com/t/${FORM_ID}  `);
    expect(questionnaireFormId()).toBe(FORM_ID);
  });

  // No env var needed: a fresh checkout and both deployments get the real form.
  it('falls back to the committed default when unset or empty', () => {
    setUrl(undefined);
    expect(questionnaireFormId()).toBe(STUDY_QUESTIONNAIRE_FORM_ID);

    setUrl('   ');
    expect(questionnaireFormId()).toBe(STUDY_QUESTIONNAIRE_FORM_ID);
  });

  // A misconfigured override must not break the study; the default still opens.
  it('falls back to the default for a value that is not a parseable link', () => {
    setUrl('https://');
    expect(questionnaireFormId()).toBe(STUDY_QUESTIONNAIRE_FORM_ID);

    setUrl('not a url/');
    expect(questionnaireFormId()).toBe(STUDY_QUESTIONNAIRE_FORM_ID);
  });

  it('ships the study form as the default', () => {
    expect(STUDY_QUESTIONNAIRE_FORM_ID).toBe('s9muKGX2zcus');
  });
});

describe('assignCohort', () => {
  it('is deterministic for the same uid', () => {
    expect(assignCohort('abc123')).toBe(assignCohort('abc123'));
  });

  it('splits roughly evenly across realistic Firebase uids', () => {
    const alphabet =
      'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let experimental = 0;
    const total = 20_000;
    for (let i = 0; i < total; i++) {
      let uid = '';
      for (let j = 0; j < 28; j++) {
        uid += alphabet[(i * 31 + j * 7) % alphabet.length];
      }
      // Vary the uid beyond the deterministic pattern above.
      uid += String(i);
      if (assignCohort(uid) === 'experimental') {
        experimental++;
      }
    }
    const share = experimental / total;
    expect(share).toBeGreaterThan(0.45);
    expect(share).toBeLessThan(0.55);
  });
});
