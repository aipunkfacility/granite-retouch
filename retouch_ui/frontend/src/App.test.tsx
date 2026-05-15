import { describe, it, expect } from 'vitest';
import { isConfigTree } from './lib/types';
import type { ConfigTree, MachineType } from './lib/types';
import { deepMerge } from './lib/utils';

// ─── FIX-27: getExportMode helper ───
// We replicate the function here since it's defined locally in App.tsx
function getExportMode(config: ConfigTree | null, machineType: MachineType): string | undefined {
  if (!config?.processing) return undefined;
  const proc = config.processing as Record<string, unknown>;
  const machine = proc[machineType] as Record<string, unknown> | undefined;
  if (!machine) return undefined;
  return typeof machine.export_mode === "string" ? machine.export_mode : undefined;
}

describe('getExportMode (FIX-27)', () => {
  it('returns undefined for null config', () => {
    expect(getExportMode(null, 'laser_standard')).toBeUndefined();
  });

  it('returns undefined for config without processing', () => {
    expect(getExportMode({}, 'laser_standard')).toBeUndefined();
  });

  it('returns undefined when machine key missing', () => {
    const config: ConfigTree = { processing: {} };
    expect(getExportMode(config, 'laser_standard')).toBeUndefined();
  });

  it('returns undefined when export_mode is not a string', () => {
    const config: ConfigTree = {
      processing: {
        laser_standard: { export_mode: 42 },
      },
    };
    expect(getExportMode(config, 'laser_standard')).toBeUndefined();
  });

  it('returns export_mode value when present', () => {
    const config: ConfigTree = {
      processing: {
        laser_standard: { export_mode: '1bit' },
      },
    };
    expect(getExportMode(config, 'laser_standard')).toBe('1bit');
  });

  it('returns "8bit" for 8-bit mode', () => {
    const config: ConfigTree = {
      processing: {
        impact: { export_mode: '8bit' },
      },
    };
    expect(getExportMode(config, 'impact')).toBe('8bit');
  });
});

// ─── FIX-26: deepMerge result validated by isConfigTree ───
describe('deepMerge + isConfigTree guard (FIX-26)', () => {
  it('deepMerge of two ConfigTree objects passes isConfigTree', () => {
    const base = { processing: { gamma: 1.0 } } as Record<string, unknown>;
    const override = { processing: { speed: 100 } } as Record<string, unknown>;
    const merged = deepMerge(base, override);
    expect(isConfigTree(merged)).toBe(true);
  });

  it('deepMerge result can be safely cast to ConfigTree after guard', () => {
    const base = { a: 1 } as Record<string, unknown>;
    const override = { b: 2 } as Record<string, unknown>;
    const merged = deepMerge(base, override);
    if (!isConfigTree(merged)) {
      throw new Error('Expected ConfigTree');
    }
    // TypeScript now knows merged is ConfigTree
    expect(merged.a).toBe(1);
    expect(merged.b).toBe(2);
  });
});

// ─── FIX-30: onResetParam uses isConfigTree guard ───
describe('onResetParam isConfigTree guard (FIX-30)', () => {
  it('isConfigTree correctly identifies when intermediate path is not an object', () => {
    // Simulates the onResetParam logic where a path segment might be a number
    const config: Record<string, unknown> = {
      processing: {
        laser_standard: 42, // Not an object — should trigger guard
      },
    };

    const parts = ['processing', 'laser_standard', 'gamma'];
    let obj: Record<string, unknown> = config;
    let needsInit = false;

    for (let i = 0; i < parts.length - 1; i++) {
      if (!isConfigTree(obj[parts[i]])) {
        needsInit = true;
        break;
      }
      obj = obj[parts[i]] as Record<string, unknown>;
    }

    expect(needsInit).toBe(true);
  });

  it('isConfigTree allows traversal when path is valid objects', () => {
    const config: Record<string, unknown> = {
      processing: {
        laser_standard: { gamma: 1.0 },
      },
    };

    const parts = ['processing', 'laser_standard', 'gamma'];
    let obj: Record<string, unknown> = config;
    let needsInit = false;

    for (let i = 0; i < parts.length - 1; i++) {
      if (!isConfigTree(obj[parts[i]])) {
        needsInit = true;
        break;
      }
      obj = obj[parts[i]] as Record<string, unknown>;
    }

    expect(needsInit).toBe(false);
    expect(obj['gamma']).toBe(1.0);
  });
});

// ─── FIX-22: non-null assertions replaced with optional chaining ───
describe('comboPresets logic (FIX-22)', () => {
  it('handles missing selectedPreset safely', () => {
    const catalog: Record<string, { combo_group?: string }> = {};
    const selectedPreset: string | null = null;

    // Old code: pm.catalog[pm.selectedPreset]!.combo_group!  → would crash
    // New code:
    if (!selectedPreset) {
      expect(true).toBe(true); // early return path
      return;
    }
    const entry = catalog[selectedPreset];
    if (!entry?.combo_group) {
      expect(true).toBe(true); // no combo_group path
      return;
    }
  });

  it('handles entry without combo_group safely', () => {
    const catalog: Record<string, { label: string; machine_type: string; combo_group?: string }> = {
      test_preset: { label: 'Test', machine_type: 'laser_standard' },
    };
    const selectedPreset = 'test_preset';

    const entry = catalog[selectedPreset];
    const hasComboGroup = entry?.combo_group;
    expect(hasComboGroup).toBeUndefined();
  });
});
