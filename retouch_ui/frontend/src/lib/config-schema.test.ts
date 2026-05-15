import { describe, it, expect } from 'vitest';
import { getMachineParams, CONFIG_SCHEMA } from './config-schema';
import type { MachineType } from './types';
import type { ParamRange } from './config-schema';

// ─── FIX-2: getMachineParams with MachineType parameter + never guard ───
describe('getMachineParams (FIX-2)', () => {
  it('returns params for laser_standard', () => {
    const params = getMachineParams('laser_standard');
    expect(params).toBeDefined();
    expect(params['stone_gamma']).toBeDefined();
    // stone_gamma is a ParamRange (has min/max/step)
    const sg = params['stone_gamma'] as ParamRange;
    expect(sg.min).toBe(0.5);
  });

  it('returns params for laser_80w', () => {
    const params = getMachineParams('laser_80w');
    expect(params).toBeDefined();
    expect(params['stone_gamma']).toBeDefined();
  });

  it('returns params for impact', () => {
    const params = getMachineParams('impact');
    expect(params).toBeDefined();
    // Impact has extra shadow params
    expect(params['shadow_noise_min']).toBeDefined();
  });

  it('returns Record<string, ParamDef> — all keys accessible by string', () => {
    const params = getMachineParams('laser_standard');
    const key: string = 'stone_gamma';
    expect(params[key]).toBeDefined();
  });

  it('never guard — compile-time exhaustiveness (runtime never hits default)', () => {
    // If this compiles, the never guard works — MachineType switch is exhaustive
    const allTypes: MachineType[] = ['laser_standard', 'laser_80w', 'impact'];
    for (const mt of allTypes) {
      const result = getMachineParams(mt);
      expect(Object.keys(result).length).toBeGreaterThan(0);
    }
  });

  it('returned objects match CONFIG_SCHEMA entries', () => {
    expect(getMachineParams('laser_standard')).toBe(CONFIG_SCHEMA.processing.laser_standard as unknown as ReturnType<typeof getMachineParams>);
    expect(getMachineParams('laser_80w')).toBe(CONFIG_SCHEMA.processing.laser_80w as unknown as ReturnType<typeof getMachineParams>);
    expect(getMachineParams('impact')).toBe(CONFIG_SCHEMA.processing.impact as unknown as ReturnType<typeof getMachineParams>);
  });
});
