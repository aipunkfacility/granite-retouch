import { describe, it, expect } from 'vitest';
import { clamp, deepMerge } from './utils';

// ─── FIX-19: clamp in lib/utils.ts ───
describe('clamp (FIX-19)', () => {
  it('returns value when within range', () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(0.5, 0, 1)).toBe(0.5);
  });

  it('clamps to min', () => {
    expect(clamp(-5, 0, 10)).toBe(0);
    expect(clamp(-0.1, 0, 1)).toBe(0);
  });

  it('clamps to max', () => {
    expect(clamp(15, 0, 10)).toBe(10);
    expect(clamp(1.5, 0, 1)).toBe(1);
  });

  it('handles min === max', () => {
    expect(clamp(5, 3, 3)).toBe(3);
    expect(clamp(1, 3, 3)).toBe(3);
  });

  it('handles negative ranges', () => {
    expect(clamp(-3, -5, -1)).toBe(-3);
    expect(clamp(-10, -5, -1)).toBe(-5);
  });
});

// ─── FIX-26: deepMerge result guarded by isConfigTree ───
describe('deepMerge (FIX-26)', () => {
  it('merges flat objects', () => {
    const base = { a: 1, b: 2 };
    const override = { b: 3, c: 4 };
    const result = deepMerge(base, override);
    expect(result).toEqual({ a: 1, b: 3, c: 4 });
  });

  it('merges nested objects recursively', () => {
    const base = { processing: { gamma: 1.0, speed: 100 } } as Record<string, unknown>;
    const override = { processing: { gamma: 1.5 } } as Record<string, unknown>;
    const result = deepMerge(base, override);
    expect(result.processing).toEqual({ gamma: 1.5, speed: 100 });
  });

  it('returns a plain object (verifiable with isConfigTree pattern)', () => {
    const base = { a: 1 };
    const override = { b: 2 };
    const result = deepMerge(base, override);
    // This is what isConfigTree checks — must be a plain object
    expect(result).not.toBeNull();
    expect(typeof result).toBe('object');
    expect(Array.isArray(result)).toBe(false);
    expect(Object.getPrototypeOf(result)).toBe(Object.prototype);
  });

  it('override replaces arrays', () => {
    const base = { items: [1, 2, 3] } as Record<string, unknown>;
    const override = { items: [4, 5] } as Record<string, unknown>;
    const result = deepMerge(base, override);
    expect(result.items).toEqual([4, 5]);
  });
});
