import { describe, expect, it } from 'bun:test';
import { markWeeklySignupOpened, weeklySignupOpened } from './weekly-signup';

function memoryStorage(): Pick<Storage, 'getItem' | 'setItem'> {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
  };
}

const broken: Pick<Storage, 'getItem' | 'setItem'> = {
  getItem: () => {
    throw new Error('blocked');
  },
  setItem: () => {
    throw new Error('blocked');
  },
};

describe('weekly signup dot', () => {
  it('stays until the first open, then never again', () => {
    const storage = memoryStorage();
    expect(weeklySignupOpened(storage)).toBe(false);
    markWeeklySignupOpened(storage);
    expect(weeklySignupOpened(storage)).toBe(true);
  });

  it('shows no dot when the browser blocks storage', () => {
    expect(weeklySignupOpened(broken)).toBe(true);
    expect(() => markWeeklySignupOpened(broken)).not.toThrow();
  });
});
