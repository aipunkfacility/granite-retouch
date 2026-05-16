/** MachineSelector — grouped dropdown по брендам + «По технологии». */

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
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const ref = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Flatten all options for keyboard navigation
  const allOptions = groups.flatMap(g => g.presets);

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

  const handleTriggerKeyDown = (e: React.KeyboardEvent) => {
    if (!open && (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      setOpen(true);
      setFocusedIndex(0);
    }
  };

  const handleListKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setFocusedIndex(prev => {
          const next = Math.min(prev + 1, allOptions.length - 1);
          optionRefs.current[next]?.focus();
          return next;
        });
        break;
      case "ArrowUp":
        e.preventDefault();
        setFocusedIndex(prev => {
          const next = Math.max(prev - 1, 0);
          optionRefs.current[next]?.focus();
          return next;
        });
        break;
      case "Escape":
        e.preventDefault();
        setOpen(false);
        break;
      case "Enter":
        e.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < allOptions.length) {
          const { key, entry } = allOptions[focusedIndex];
          handleSelect(key, entry);
        }
        break;
      case "Tab":
        // Focus trap: wrap Tab from last → first, Shift+Tab from first → close
        e.preventDefault();
        if (e.shiftKey) {
          if (focusedIndex <= 0) {
            setOpen(false);
          } else {
            const prev = focusedIndex - 1;
            setFocusedIndex(prev);
            optionRefs.current[prev]?.focus();
          }
        } else {
          if (focusedIndex >= allOptions.length - 1) {
            setOpen(false);
          } else {
            const next = focusedIndex + 1;
            setFocusedIndex(next);
            optionRefs.current[next]?.focus();
          }
        }
        break;
    }
  };

  // Reset focusedIndex when opening
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (open) setFocusedIndex(0);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        onKeyDown={handleTriggerKeyDown}
        aria-expanded={open}
        aria-haspopup="listbox"
        id="machine-selector-trigger"
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium transition-colors duration-200
          ${colors.bg} ${colors.border} hover:opacity-90`}
      >
        <span className={`w-2 h-2 rounded-full ${colors.dot}`} />
        <span>{currentLabel || "Выберите станок"}</span>
        <i className={`ri-arrow-${open ? "up" : "down"}-s-line`} />
      </button>

      {open && (
        <div
          role="listbox"
          aria-labelledby="machine-selector-trigger"
          onKeyDown={handleListKeyDown}
          className="absolute top-full left-0 mt-1 w-72 bg-bg-card border border-border rounded-lg shadow-lg z-50 max-h-[70vh] overflow-y-auto"
        >
          {groups.map((group) => {
            // Find the starting index for this group's options in the flat list
            return (
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
                  const flatIndex = allOptions.findIndex(o => o.key === key);
                  return (
                    <button
                      key={key}
                      ref={(el) => { optionRefs.current[flatIndex] = el; }}
                      onClick={() => handleSelect(key, entry)}
                      role="option"
                      aria-selected={isSelected}
                       className={`w-full flex items-center gap-2 px-4 py-2 text-sm text-left transition-colors duration-200
                        ${isSelected ? "bg-accent-blue/10 text-accent-blue" : "hover:bg-bg-hover text-text-primary"}`}
                    >
                      <span className={`w-2 h-2 rounded-full shrink-0 ${itemColors.dot}`} />
                      <span className="flex-1">{entry.label}</span>
                      {entry.alert && (
                        <span className="text-xs text-accent-orange bg-accent-orange/10 border border-accent-orange/30 px-1.5 py-0.5 rounded-lg"
                          title={entry.alert}>
                          <i className="ri-error-warning-line text-xs" />
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
