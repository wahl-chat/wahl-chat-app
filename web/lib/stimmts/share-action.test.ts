import { describe, expect, it } from 'bun:test';
import { type ShareEnv, shareText } from './share-action';

const TEXT = "Stimmt's? #1 · Energie · 3/5";

// Records what was shared or copied, and can be told to fail.
function fakeEnv(options: {
  share?: 'ok' | 'abort' | 'blocked' | 'missing';
  clipboard?: 'ok' | 'denied' | 'missing';
}) {
  const calls: { shared: string[]; copied: string[] } = {
    shared: [],
    copied: [],
  };
  const env: ShareEnv = {};
  const share = options.share ?? 'missing';
  const clipboard = options.clipboard ?? 'missing';

  if (share !== 'missing') {
    env.share = async ({ text }) => {
      if (share === 'abort') {
        throw new DOMException('cancelled', 'AbortError');
      }
      if (share === 'blocked') {
        throw new DOMException('not allowed', 'NotAllowedError');
      }
      calls.shared.push(text);
    };
  }
  if (clipboard !== 'missing') {
    env.writeText = async (text) => {
      if (clipboard === 'denied') {
        throw new Error('denied');
      }
      calls.copied.push(text);
    };
  }
  return { env, calls };
}

describe('shareText', () => {
  it('uses the share sheet when there is one', async () => {
    const { env, calls } = fakeEnv({ share: 'ok', clipboard: 'ok' });
    expect(await shareText(TEXT, env)).toBe('shared');
    expect(calls.shared).toEqual([TEXT]);
    expect(calls.copied).toEqual([]);
  });

  it('treats closing the share sheet as cancelled, not as a failure', async () => {
    const { env, calls } = fakeEnv({ share: 'abort', clipboard: 'ok' });
    expect(await shareText(TEXT, env)).toBe('cancelled');
    expect(calls.copied).toEqual([]);
  });

  it('copies instead when the browser blocks sharing', async () => {
    const { env, calls } = fakeEnv({ share: 'blocked', clipboard: 'ok' });
    expect(await shareText(TEXT, env)).toBe('copied');
    expect(calls.copied).toEqual([TEXT]);
  });

  it('copies when there is no share sheet at all', async () => {
    const { env, calls } = fakeEnv({ clipboard: 'ok' });
    expect(await shareText(TEXT, env)).toBe('copied');
    expect(calls.copied).toEqual([TEXT]);
  });

  it('reports failure when nothing works, so the text can be shown', async () => {
    expect(await shareText(TEXT, fakeEnv({ clipboard: 'denied' }).env)).toBe(
      'failed',
    );
    expect(await shareText(TEXT, fakeEnv({}).env)).toBe('failed');
    expect(
      await shareText(
        TEXT,
        fakeEnv({ share: 'blocked', clipboard: 'denied' }).env,
      ),
    ).toBe('failed');
  });
});
