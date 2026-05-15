/** MachineSelector — grouped dropdown по брендам + «По технологии».
 * Заменяет machine-switch.tsx.
 */

import { useState, useEffect, useRef } from "react";
import type { MachineType, CatalogGroup, PresetCatalogEntry, ConfigTree } from "../lib/types";
import { MACHINE_THEME } from "../lib/machine-theme";

interface MachineSelectorProps {
  groups: CatalogGroup[];
  selectedPreset: string | null;
  machineType: MachineType;
  presetsCache: Record<string, ConfigTree>;
  onSelect: (presetKey: string, presetConfig: ConfigTree, machineType: MachineType) => void;
}

export function MachineSelector({ groups, selectedPreset, machineType, presetsCache, onSelect }: MachineSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Закрыть при клике вне
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Найти label текущего пресета
  const currentLabel = (() => {
    for (const group of groups) {
      for (const p of group.presets) {
        if (p.key === selectedPreset) return p.entry.label;
      }
    }
    return null;
  })();

  const handleSelect = (presetKey: string, entry: PresetCatalogEntry) => {
    const config = presetsCache[presetKey];
    if (config) onSelect(presetKey, config, entry.machine_type);
    setOpen(false);
  };

  const colors = MACHINE_THEME[machineType];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors
          ${colors.bg} ${colors.border} hover:opacity-90`}
      >
        <span className={`w-2 h-2 rounded-full ${colors.dot}`} />
        <span>{currentLabel || "Выберите станок"}</span>
        <i className={`ri-arrow-${open ? "up" : "down"}-s-line`} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-72 bg-bg-card border border-border rounded-lg shadow-lg z-50 max-h-[70vh] overflow-y-auto">
          {groups.map((group) => (
            <div key={group.title}>
              {/* Заголовок группы */}
              <div className={`px-3 py-1.5 text-xs font-semibold text-text-muted uppercase tracking-wide
                ${group.type === "technology" ? "border-t border-border mt-1 pt-2" : ""}
                ${group.type !== "technology" ? "mt-1" : ""}`}>
                {group.type === "technology" && (
                  <span className="text-text-muted/50 mr-1">──</span>
                )}
                {group.title}
              </div>
              {/* Элементы группы */}
              {group.presets.map(({ key, entry }) => {
                const itemColors = MACHINE_THEME[entry.machine_type];
                const isSelected = key === selectedPreset;
                return (
                  <button
                    key={key}
                    onClick={() => handleSelect(key, entry)}
                    className={`w-full flex items-center gap-2 px-4 py-2 text-sm text-left transition-colors
                      ${isSelected ? "bg-accent-blue/10 text-accent-blue" : "hover:bg-bg-hover text-text-primary"}`}
                  >
                    <span className={`w-2 h-2 rounded-full shrink-0 ${itemColors.dot}`} />
                    <span className="flex-1">{entry.label}</span>
                    {entry.alert && (
                      <span className="text-xs text-yellow-600 bg-yellow-50 border border-yellow-200 px-1.5 py-0.5 rounded"
                        title={entry.alert}>
                        ⚠️
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
