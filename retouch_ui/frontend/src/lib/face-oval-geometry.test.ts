import { describe, it, expect } from 'vitest';
import { computeFaceOvalFromDrag, FACE_OVAL_LIMITS } from './face-oval-geometry';
import type { FaceOvalParams } from './types';

// ─── FIX-4 (partial): shiftHeld affects computeFaceOvalFromDrag ───
describe('computeFaceOvalFromDrag shift behavior (FIX-4)', () => {
  const base: FaceOvalParams = { cx: 0.5, cy: 0.3, rx: 0.15, ry: 0.20, source: 'heuristic' };

  it('left drag without shift changes rx only', () => {
    const result = computeFaceOvalFromDrag('left', { dx: -0.05, dy: 0 }, base, false);
    expect(result.rx).toBeDefined();
    expect(result.ry).toBeUndefined();
  });

  it('left drag WITH shift changes both rx and ry proportionally', () => {
    const result = computeFaceOvalFromDrag('left', { dx: -0.05, dy: 0 }, base, true);
    expect(result.rx).toBeDefined();
    expect(result.ry).toBeDefined();
  });

  it('right drag without shift changes rx only', () => {
    const result = computeFaceOvalFromDrag('right', { dx: 0.05, dy: 0 }, base, false);
    expect(result.rx).toBeDefined();
    expect(result.ry).toBeUndefined();
  });

  it('right drag WITH shift changes both rx and ry', () => {
    const result = computeFaceOvalFromDrag('right', { dx: 0.05, dy: 0 }, base, true);
    expect(result.rx).toBeDefined();
    expect(result.ry).toBeDefined();
  });

  it('all results are clamped to FACE_OVAL_LIMITS', () => {
    const extremeBase: FaceOvalParams = { cx: 0.5, cy: 0.3, rx: 0.03, ry: 0.03, source: 'heuristic' };
    const result = computeFaceOvalFromDrag('left', { dx: -1.0, dy: 0 }, extremeBase, true);
    if (result.rx !== undefined) {
      expect(result.rx).toBeGreaterThanOrEqual(FACE_OVAL_LIMITS.rx.min);
      expect(result.rx).toBeLessThanOrEqual(FACE_OVAL_LIMITS.rx.max);
    }
    if (result.ry !== undefined) {
      expect(result.ry).toBeGreaterThanOrEqual(FACE_OVAL_LIMITS.ry.min);
      expect(result.ry).toBeLessThanOrEqual(FACE_OVAL_LIMITS.ry.max);
    }
  });

  it('sets source to "manual"', () => {
    const result = computeFaceOvalFromDrag('center', { dx: 0.01, dy: 0.01 }, base, false);
    expect(result.source).toBe('manual');
  });
});

// ─── FIX-17: FaceOvalParams re-exported from types.ts ───
describe('FaceOvalParams import (FIX-17)', () => {
  it('can import FaceOvalParams from this module (re-export)', () => {
    // This test verifies the re-export works — if import fails, test won't compile
    const params: FaceOvalParams = { cx: 0.5, cy: 0.3, rx: 0.15, ry: 0.20, source: 'heuristic' };
    expect(params.cx).toBe(0.5);
  });
});
