import { describe, it, expect } from 'vitest';
import { isConfigTree } from './types';
import type { MachineType, ConfigTree } from './types';

// ─── FIX-0.1: trivial test (infrastructure) ───
describe('types', () => {
  it('should compile type aliases without error', () => {
    const mt: MachineType = 'laser_standard';
    const config: ConfigTree = { gamma: 1.0 };
    expect(mt).toBe('laser_standard');
    expect(config.gamma).toBe(1.0);
  });
});

// ─── FIX-14: isConfigTree type guard with prototype check ───
describe('isConfigTree (FIX-14)', () => {
  it('returns true for plain objects', () => {
    expect(isConfigTree({})).toBe(true);
    expect(isConfigTree({ a: 1, b: 'hello' })).toBe(true);
    expect(isConfigTree({ nested: { inner: 42 } })).toBe(true);
  });

  it('returns true for Object.create(null)', () => {
    const noProto = Object.create(null);
    noProto.foo = 'bar';
    expect(isConfigTree(noProto)).toBe(true);
  });

  it('returns false for null', () => {
    expect(isConfigTree(null)).toBe(false);
  });

  it('returns false for arrays', () => {
    expect(isConfigTree([])).toBe(false);
    expect(isConfigTree([1, 2, 3])).toBe(false);
  });

  it('returns false for primitives', () => {
    expect(isConfigTree(42)).toBe(false);
    expect(isConfigTree('string')).toBe(false);
    expect(isConfigTree(true)).toBe(false);
    expect(isConfigTree(undefined)).toBe(false);
  });

  it('returns false for class instances (Date, Map, Set, Error)', () => {
    expect(isConfigTree(new Date())).toBe(false);
    expect(isConfigTree(new Map())).toBe(false);
    expect(isConfigTree(new Set())).toBe(false);
    expect(isConfigTree(new Error('test'))).toBe(false);
  });

  it('returns false for JSON-like but non-plain objects', () => {
    class FakeObj { x = 1; }
    expect(isConfigTree(new FakeObj())).toBe(false);
  });

  it('narrows type correctly', () => {
    const val: unknown = { gamma: 1.0 };
    if (isConfigTree(val)) {
      // TypeScript should allow access
      expect(val['gamma']).toBe(1.0);
    } else {
      expect.unreachable('Should be ConfigTree');
    }
  });
});
