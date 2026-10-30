import { describe, expect, it } from 'bun:test';
import { parseStimmtsStatus, resolveAvailability } from './availability';

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

describe('resolveAvailability', () => {
  const on = { enabled: true, launchDate: '2026-11-15' } as const;

  it('is off whatever the date', () => {
    expect(
      resolveAvailability({ enabled: false }, new Date('2026-11-20T12:00:00Z')),
    ).toEqual({ status: 'off' });
  });

  it('has not started before the launch date', () => {
    expect(resolveAvailability(on, new Date('2026-11-14T12:00:00Z'))).toEqual({
      status: 'not-started',
      launchDate: '2026-11-15',
    });
  });

  it('runs from the launch date on', () => {
    for (const now of ['2026-11-15T12:00:00Z', '2027-03-01T12:00:00Z']) {
      expect(resolveAvailability(on, new Date(now))).toEqual({
        status: 'running',
        launchDate: '2026-11-15',
      });
    }
  });

  it('starts at Berlin midnight, not UTC midnight', () => {
    // 23:30 UTC on 14 November is 00:30 on the 15th in Berlin (UTC+1).
    expect(
      resolveAvailability(on, new Date('2026-11-14T23:30:00Z')).status,
    ).toBe('running');
    expect(
      resolveAvailability(on, new Date('2026-11-14T22:59:59Z')).status,
    ).toBe('not-started');
  });
});
