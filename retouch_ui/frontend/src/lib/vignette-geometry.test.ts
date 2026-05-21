import { describe, it, expect } from 'vitest';
import {
  computeParamsFromTopDragShift,
  computeParamsFromDrag,
  VIGNETTE_LIMITS,
  type VignetteParams,
} from './vignette-geometry';

// ─── FIX-7: computeParamsFromTopDragShift signature without imageWidth ───
describe('computeParamsFromTopDragShift (FIX-7)', () => {
  const defaultParams: VignetteParams = {
    enabled: true,
    vertical_offset: 0.1,
    vertical_diameter: 0.5,
    blur_radius: 60,
    headroom: 0.6,
    horizontal_oversize: 0.2,
  };
  const imageHeight = 1000;

  it('computes vertical_diameter from drag without imageWidth parameter', () => {
    // FIX-7: imageWidth was removed from signature
    const result = computeParamsFromTopDragShift(
      { x: 0, y: 200 },  // newPosition
      imageHeight,
      defaultParams,
    );
    expect(result.vertical_diameter).toBeDefined();
    expect(typeof result.vertical_diameter).toBe('number');
  });

  it('clamps result to VIGNETTE_LIMITS', () => {
    const result = computeParamsFromTopDragShift(
      { x: 0, y: -500 },  // way above the image
      imageHeight,
      defaultParams,
    );
    if (result.vertical_diameter !== undefined) {
      expect(result.vertical_diameter).toBeGreaterThanOrEqual(VIGNETTE_LIMITS.vertical_diameter.min);
      expect(result.vertical_diameter).toBeLessThanOrEqual(VIGNETTE_LIMITS.vertical_diameter.max);
    }
  });

  it('only returns vertical_diameter (not other params)', () => {
    const result = computeParamsFromTopDragShift(
      { x: 0, y: 300 },
      imageHeight,
      defaultParams,
    );
    expect(Object.keys(result)).toEqual(['vertical_diameter']);
  });
});

// ─── FIX-19 (partial): clamp imported from utils, used correctly ───
describe('computeParamsFromDrag uses clamp (FIX-19)', () => {
  const defaultParams: VignetteParams = {
    enabled: true,
    vertical_offset: 0.1,
    vertical_diameter: 0.5,
    blur_radius: 60,
    headroom: 0.6,
    horizontal_oversize: 0.2,
  };

  it('top handle clamps headroom to limits', () => {
    const result = computeParamsFromDrag(
      'top',
      { x: 0, y: -10000 },  // way above — should clamp
      1000,
      1000,
      defaultParams,
    );
    if (result.headroom !== undefined) {
      expect(result.headroom).toBeGreaterThanOrEqual(VIGNETTE_LIMITS.headroom.min);
      expect(result.headroom).toBeLessThanOrEqual(VIGNETTE_LIMITS.headroom.max);
    }
  });
});
