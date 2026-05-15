import { describe, it, expect } from 'vitest';
import { MACHINE_THEME } from './machine-theme';
import type { MachineType } from './types';

// ─── FIX-16: MACHINE_THEME — unified module replaces duplicate MACHINE_COLORS ───
describe('MACHINE_THEME (FIX-16)', () => {
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

  it('impact has orange theme', () => {
    expect(MACHINE_THEME.impact.bg).toContain('orange');
    expect(MACHINE_THEME.impact.border).toContain('orange');
  });

  it('laser_standard has green theme', () => {
    expect(MACHINE_THEME.laser_standard.bg).toContain('green');
    expect(MACHINE_THEME.laser_standard.border).toContain('green');
  });

  it('laser_80w has red theme', () => {
    expect(MACHINE_THEME.laser_80w.bg).toContain('red');
    expect(MACHINE_THEME.laser_80w.border).toContain('red');
  });

  it('has exactly 3 entries (one per MachineType)', () => {
    expect(Object.keys(MACHINE_THEME)).toHaveLength(3);
  });
});
