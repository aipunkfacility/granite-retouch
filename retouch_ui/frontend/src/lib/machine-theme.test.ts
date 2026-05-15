import { describe, it, expect } from 'vitest';
import { MACHINE_THEME } from './machine-theme';
import type { MachineType } from './types';

describe('MACHINE_THEME', () => {
  it('has entry for every MachineType', () => {
    const types: MachineType[] = ['laser_standard', 'laser_80w', 'impact'];
    for (const mt of types) {
      expect(MACHINE_THEME[mt]).toBeDefined();
    }
  });

  it('each entry has all required fields', () => {
    for (const mt of Object.keys(MACHINE_THEME) as MachineType[]) {
      const theme = MACHINE_THEME[mt];
      expect(theme.bg).toBeTruthy();
      expect(theme.border).toBeTruthy();
      expect(theme.dot).toBeTruthy();
      expect(theme.icon).toBeTruthy();
      expect(theme.label).toBeTruthy();
    }
  });

  it('has exactly 3 entries (one per MachineType)', () => {
    expect(Object.keys(MACHINE_THEME)).toHaveLength(3);
  });

  it('no light palette classes (*-50) remain', () => {
    for (const mt of Object.keys(MACHINE_THEME) as MachineType[]) {
      const theme = MACHINE_THEME[mt];
      expect(theme.bg).not.toMatch(/\*-50/);
      expect(theme.border).not.toMatch(/\*-200/);
    }
  });

  it('impact uses accent-orange dark palette', () => {
    expect(MACHINE_THEME.impact.bg).toContain('accent-orange');
    expect(MACHINE_THEME.impact.border).toContain('accent-orange');
    expect(MACHINE_THEME.impact.dot).toContain('accent-orange');
  });

  it('laser_standard uses accent-green dark palette', () => {
    expect(MACHINE_THEME.laser_standard.bg).toContain('accent-green');
    expect(MACHINE_THEME.laser_standard.border).toContain('accent-green');
    expect(MACHINE_THEME.laser_standard.dot).toContain('accent-green');
  });

  it('laser_80w uses accent-red dark palette', () => {
    expect(MACHINE_THEME.laser_80w.bg).toContain('accent-red');
    expect(MACHINE_THEME.laser_80w.border).toContain('accent-red');
    expect(MACHINE_THEME.laser_80w.dot).toContain('accent-red');
  });
});
