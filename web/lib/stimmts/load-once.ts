/**
 * Loads something once per server instance and keeps it, but forgets a
 * failure, so one bad moment (a font host that is down) is retried by the
 * next request instead of being remembered. Null means "not this time".
 */
export function createLoadOnce<T>(load: () => Promise<T>) {
  let pending: Promise<T> | null = null;
  return async (): Promise<T | null> => {
    pending ??= load();
    try {
      return await pending;
    } catch (error) {
      console.error('Stimmts: loading failed, will retry', error);
      pending = null;
      return null;
    }
  };
}
