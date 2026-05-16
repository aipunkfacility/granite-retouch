/** MaterialSelector — чипсы-кнопки для выбора материала.
 * Подсказки из MATERIAL_PROFILES, автокоррекция через POST /api/material/apply.
 */

import { useCallback, useEffect } from "react";
import type { MaterialType, MachineType, MaterialProfile, MaterialChange, ConfigTree } from "../lib/types";
import { useToast } from "./toast-provider";

/** Материалы в порядке отображения */
const MATERIAL_ORDER: MaterialType[] = ["granite", "gabbro", "basalt", "marble", "acrylic"];

/** Русские названия */
const MATERIAL_LABELS: Record<MaterialType, string> = {
  granite: "Гранит",
  gabbro: "Габбро",
  basalt: "Базальт",
  marble: "Мрамор",
  acrylic: "Акрил",
};

interface Props {
  material: MaterialType;
  machineType: MachineType;
  profiles: Record<string, MaterialProfile>;
  materialChanges: MaterialChange[];
  validationWarnings: string[];
  activeHint: string | null;
  onSelect: (material: MaterialType, currentConfig?: ConfigTree) => Promise<{ success: boolean; validationWarnings: string[] }>;
  currentConfig?: ConfigTree;
  /** Compact mode: chips only, no title/details/hints */
  compact?: boolean;
}

export function MaterialSelector({
  material,
  machineType,
  profiles,
  materialChanges,
  activeHint,
  onSelect,
  currentConfig,
  compact,
}: Props) {
  const { showToast } = useToast();

  const handleSelect = useCallback(async (mat: MaterialType) => {
    const { success, validationWarnings: warnings } = await onSelect(mat, currentConfig);
    if (!success) {
      const errorMsg = warnings.find(w => w.startsWith("ERROR:"))?.replace("ERROR: ", "") || "Несовместимая комбинация";
      showToast(errorMsg, { type: 'error', duration: 4000 });
    }
  }, [onSelect, currentConfig, showToast]);

  // Показать тост с автокоррекциями при изменении materialChanges
  const formatChangesToast = useCallback((changes: MaterialChange[], mat: MaterialType): string | null => {
    if (changes.length === 0) return null;
    if (changes.length === 1) {
      const c = changes[0];
      const reason = c.reason ? ` (${c.reason})` : "";
      return `${c.param} ${c.old} → ${c.new}${reason}`;
    }
    const parts = changes.map(c => `${c.param} ${c.old} → ${c.new}`);
    return `Параметры скорректированы под ${MATERIAL_LABELS[mat]}: ${parts.join(", ")}`;
  }, []);

  // Автопоказ при изменении materialChanges
  useEffect(() => {
    if (materialChanges.length > 0) {
      const msg = formatChangesToast(materialChanges, material);
      if (msg) {
        showToast(msg, { type: 'info', duration: 5000 });
      }
    }
  }, [materialChanges, material, formatChangesToast, showToast]);

  const profile = profiles[material];

  // Проверка: есть ли hint для текущего материала+machine_type
  const isIncompatible = profile?.incompatible_machine_types?.includes(machineType);

  return (
    <div className={compact ? "" : "space-y-2"}>
      {!compact && <h4 className="text-sm font-heading font-semibold text-text-primary">Материал</h4>}

      {/* Чипсы */}
      <div className="flex flex-wrap gap-1.5">
        {MATERIAL_ORDER.map((mat) => {
          const isActive = mat === material;
          const matProfile = profiles[mat];
          const isWarning = matProfile?.hints?.[machineType] && mat !== "acrylic";
          const isAlert = mat === "acrylic" || matProfile?.incompatible_machine_types?.includes(machineType);

          return (
            <button
              key={mat}
              onClick={() => handleSelect(mat)}
              aria-pressed={isActive}
              aria-label={`Материал: ${MATERIAL_LABELS[mat]}`}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all duration-200 border
                ${isActive
                  ? "bg-accent-blue text-white border-accent-blue"
                  : isAlert
                    ? "bg-accent-orange/10 text-accent-orange border-accent-orange/30 hover:bg-accent-orange/20"
                    : isWarning
                      ? "bg-accent-orange/10 text-accent-orange border-accent-orange/30 hover:bg-accent-orange/20"
                      : "bg-bg-input text-text-secondary border-border hover:bg-bg-hover hover:text-text-primary"
                }`}
            >
              {MATERIAL_LABELS[mat]}
              {isAlert && mat === "acrylic" && <i className="ri-alert-line ml-1 text-xs" />}
            </button>
          );
        })}
      </div>

      {!compact && profile && (
        <div className="text-xs text-text-muted space-y-0.5">
          <div>
            <i className="ri-lightbulb-line mr-0.5" /> {MATERIAL_LABELS[material]}: step {profile.step_mm_range[0].toFixed(3)}–{profile.step_mm_range[1].toFixed(3)},
            gamma {profile.stone_gamma_range[0].toFixed(2)}–{profile.stone_gamma_range[1].toFixed(2)}
          </div>
          {profile.notes && (
            <div className="text-text-muted/80">{profile.notes}</div>
          )}
        </div>
      )}

      {!compact && activeHint && (
        <div className={`text-xs px-2 py-1 rounded-lg border
          ${isIncompatible
            ? "bg-accent-red/10 text-accent-red border-accent-red/30"
            : "bg-accent-orange/10 text-accent-orange border-accent-orange/30"
          }`}>
          <i className={isIncompatible ? "ri-forbid-line mr-0.5" : "ri-alert-line mr-0.5"} /> {activeHint}
        </div>
      )}
    </div>
  );
}
