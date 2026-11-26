import { describe, expect, it } from 'bun:test';
import { type StatusState, parseStimmtsStatus, resolveLaunch } from './status';

describe('parseStimmtsStatus', () => {
  it('reads an enabled switch with its launch date', () => {
    expect(
      parseStimmtsStatus({ enabled: true, launch_date: '2026-11-15' }),
    ).toEqual({ enabled: true, launchDate: '2026-11-15' });
  });

  it('is off when the doc is missing or not an object', () => {
    for (const data of [undefined, null, 'on', 1, true]) {
      expect(parseStimmtsStatus(data)).toEqual({ enabled: false });
    }
  });

  it('is off unless enabled is exactly true', () => {
    for (const enabled of [false, 'true', 1, undefined]) {
      expect(
        parseStimmtsStatus({ enabled, launch_date: '2026-11-15' }),
      ).toEqual({ enabled: false });
    }
  });

  it('is off when the launch date is missing or not a real date', () => {
    for (const launch_date of [
      undefined,
      '',
      '15.11.2026',
      '2026-11-15T00:00:00Z',
      '2026-02-31',
      20261115,
    ]) {
      expect(parseStimmtsStatus({ enabled: true, launch_date })).toEqual({
        enabled: false,
      });
    }
  });
});

describe('resolveLaunch', () => {
  const TODAY = '2026-11-03';
  const on: StatusState = {
    kind: 'known',
    status: { enabled: true, launchDate: '2026-11-15' },
  };
  const off: StatusState = { kind: 'known', status: { enabled: false } };
  const unreachable: StatusState = { kind: 'unreachable' };

  it('follows the switch', () => {
    expect(resolveLaunch(on, false, TODAY)).toEqual({
      kind: 'on',
      launchDate: '2026-11-15',
    });
    expect(resolveLaunch(off, false, TODAY)).toEqual({ kind: 'off' });
    expect(resolveLaunch(unreachable, false, TODAY)).toEqual(unreachable);
    expect(resolveLaunch({ kind: 'loading' }, false, TODAY)).toEqual({
      kind: 'loading',
    });
  });

  it('keeps the real launch date in preview', () => {
    expect(resolveLaunch(on, true, TODAY)).toEqual({
      kind: 'on',
      launchDate: '2026-11-15',
    });
  });

  it('starts today in preview when the switch is off or out of reach', () => {
    for (const state of [off, unreachable]) {
      expect(resolveLaunch(state, true, TODAY)).toEqual({
        kind: 'on',
        launchDate: TODAY,
      });
    }
  });

  it('still waits for the switch in preview', () => {
    expect(resolveLaunch({ kind: 'loading' }, true, TODAY)).toEqual({
      kind: 'loading',
    });
  });
});
