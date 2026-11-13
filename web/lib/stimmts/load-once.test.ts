import { describe, expect, it, spyOn } from 'bun:test';
import { createLoadOnce } from './load-once';

describe('createLoadOnce', () => {
  it('loads once and shares the result, even between parallel callers', async () => {
    let loads = 0;
    const get = createLoadOnce(async () => {
      loads += 1;
      return 'fonts';
    });
    expect(await Promise.all([get(), get()])).toEqual(['fonts', 'fonts']);
    expect(await get()).toBe('fonts');
    expect(loads).toBe(1);
  });

  it('gives null on a failure and tries again next time', async () => {
    const quiet = spyOn(console, 'error').mockImplementation(() => {});
    let loads = 0;
    const get = createLoadOnce(async () => {
      loads += 1;
      if (loads === 1) {
        throw new Error('font host down');
      }
      return 'fonts';
    });
    expect(await get()).toBeNull();
    expect(await get()).toBe('fonts');
    expect(loads).toBe(2);
    quiet.mockRestore();
  });
});
