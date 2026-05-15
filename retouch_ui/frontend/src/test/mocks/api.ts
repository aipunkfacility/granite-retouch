import { vi } from 'vitest';

export const mockFetchPresets = vi.fn().mockResolvedValue({
  presets: [
    { name: 'test_preset', config: { processing: { laser_standard: { gamma: 1.0 } } } },
  ],
});

export const mockFetchMaterialApply = vi.fn().mockResolvedValue({
  config_patch: {},
  changes: [],
  validation_warnings: [],
  active_hint: null,
});

export const mockFetchPresetCatalog = vi.fn().mockResolvedValue({
  catalog: {
    test_preset: {
      label: 'Test Preset',
      category: 'technology',
      machine_type: 'laser_standard',
    },
  },
});
