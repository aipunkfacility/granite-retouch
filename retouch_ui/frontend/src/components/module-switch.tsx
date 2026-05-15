/** ModuleSwitch — переключатель модулей для комби-станков.
 * Появляется только если у выбранного пресета есть combo_group.
 */

import type { MachineType, PresetCatalogEntry, ConfigTree } from "../lib/types";
import { MACHINE_THEME } from "../lib/machine-theme";

interface Props {
  comboPresets: { key: string; entry: PresetCatalogEntry }[];
  selectedPreset: string | null;
  presetsCache: Record<string, ConfigTree>;
  onSelect: (presetKey: string, presetConfig: ConfigTree, machineType: MachineType) => void;
}

export function ModuleSwitch({ comboPresets, selectedPreset, presetsCache, onSelect }: Props) {
  if (comboPresets.length <= 1) return null;

  const handleSwitch = (presetKey: string, entry: PresetCatalogEntry) => {
    const config = presetsCache[presetKey];
    if (config) onSelect(presetKey, config, entry.machine_type);
  };

  return (
    <div className="flex gap-1 mt-2">
      {comboPresets.map(({ key, entry }) => {
        const colors = MACHINE_THEME[entry.machine_type];
        const isActive = key === selectedPreset;
        return (
          <button
            key={key}
            onClick={() => handleSwitch(key, entry)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors border
              ${isActive
                ? `${colors.bg} ${colors.border} text-text-primary`
                : "bg-bg-input border-border text-text-muted hover:text-text-secondary"
              }`}
          >
            <span className={`w-2 h-2 rounded-full ${colors.dot}`} />
            {colors.label}
            {entry.alert && (
              <span className="text-xs text-yellow-600" title={entry.alert}>⚠️</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
