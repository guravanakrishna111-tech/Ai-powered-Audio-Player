import { describe, expect, it } from 'vitest';
import { formatTime } from './AudioEngine';

describe('formatTime', () => {
  it('formats seconds into mm:ss', () => {
    expect(formatTime(0)).toBe('0:00');
    expect(formatTime(65.4)).toBe('1:05');
    expect(formatTime(3599)).toBe('59:59');
  });

  it('handles non-finite values safely', () => {
    expect(formatTime(Number.NaN)).toBe('0:00');
    expect(formatTime(Number.POSITIVE_INFINITY)).toBe('0:00');
  });
});
