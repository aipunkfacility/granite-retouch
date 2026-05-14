/** ModuleSwitch — переключатель модулей для комби-станков.
 * Появляется только если у выбранного пресета есть combo_group.
 */

import type { MachineType, PresetCatalogEntry, ConfigTree } from "../lib/types";
import { fetchPresets } from "../lib/api";

/** Цветовая кодировка machine_type */
const MACHINE_COLORS: Record<MachineType, { bg: string; border: string; dot: string; label: string }> = {
  impact: { bg: "bg-orange-50", border: "border-orange-200", dot: "bg-orange-400", label: "Ударный" },
  laser_standard: { bg: "bg-green-50", border: "border-green-200", dot: "bg-green-400", label: "CO2 40W" },
  laser_80w: { bg: "bg-red-50", border: "border-red-200", dot: "bg-red-400", label: "Диод 80W" },
};

interface Props {
  comboPresets: { key: string; entry: PresetCatalogEntry }[];
  selectedPreset: string | null;
  onSelect: (presetKey: string, presetConfig: ConfigTree, machineType: MachineType) => void;
}

export function ModuleSwitch({ comboPresets, selectedPreset, onSelect }: Props) {
  if (comboPresets.length <= 1) return null;

  const handleSwitch = async (presetKey: string, entry: PresetCatalogEntry) => {
    try {
      const data = await fetchPresets();
      const found = data.presets.find(p => p.name === presetKey);
      if (found) {
        onSelect(presetKey, found.config, entry.machine_type);
      }
    } catch {
      // Silent fail
    }
  };

  return (
    <div className="flex gap-1 mt-2">
      {comboPresets.map(({ key, entry }) => {
        const colors = MACHINE_COLORS[entry.machine_type];
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
