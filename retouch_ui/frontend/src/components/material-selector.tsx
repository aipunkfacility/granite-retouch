/** MaterialSelector — чипсы-кнопки для выбора материала.
 * Подсказки из MATERIAL_PROFILES, автокоррекция через POST /api/material/apply.
 */

import { useState, useCallback } from "react";
import type { MaterialType, MachineType, MaterialProfile, MaterialChange, ConfigTree } from "../lib/types";

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
  onSelect: (material: MaterialType, currentConfig?: ConfigTree) => Promise<boolean>;
  currentConfig?: ConfigTree;
}

export function MaterialSelector({
  material,
  machineType,
  profiles,
  materialChanges,
  validationWarnings,
  activeHint,
  onSelect,
  currentConfig,
}: Props) {
  const [toast, setToast] = useState<string | null>(null);
  const [toastType, setToastType] = useState<"info" | "warning" | "error">("info");

  const handleSelect = useCallback(async (mat: MaterialType) => {
    const success = await onSelect(mat, currentConfig);
    if (!success) {
      // Выбор заблокирован (ERROR) — показываем красный тост
      const errorMsg = validationWarnings.find(w => w.startsWith("ERROR:")) || "Несовместимая комбинация";
      setToast(errorMsg.replace("ERROR: ", ""));
      setToastType("error");
      setTimeout(() => setToast(null), 4000);
    }
  }, [onSelect, currentConfig, validationWarnings]);

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

  // Показать тост если есть changes
  const showToast = useCallback((changes: MaterialChange[], mat: MaterialType) => {
    const msg = formatChangesToast(changes, mat);
    if (msg) {
      setToast(msg);
      setToastType("info");
      setTimeout(() => setToast(null), 5000);
    }
  }, [formatChangesToast]);

  // Автопоказ при изменении materialChanges
  if (materialChanges.length > 0 && !toast) {
    showToast(materialChanges, material);
  }

  const profile = profiles[material];

  // Проверка: есть ли hint для текущего материала+machine_type
  const isIncompatible = profile?.incompatible_machine_types?.includes(machineType);

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold text-text-primary">Материал</h4>

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
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all border
                ${isActive
                  ? "bg-accent-blue text-white border-accent-blue"
                  : isAlert
                    ? "bg-yellow-50 text-yellow-700 border-yellow-200 hover:bg-yellow-100"
                    : isWarning
                      ? "bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100"
                      : "bg-bg-input text-text-secondary border-border hover:bg-bg-hover hover:text-text-primary"
                }`}
            >
              {MATERIAL_LABELS[mat]}
              {isAlert && mat === "acrylic" && <span className="ml-1">⚠️</span>}
            </button>
          );
        })}
      </div>

      {/* Подсказка профиля */}
      {profile && (
        <div className="text-xs text-text-muted space-y-0.5">
          <div>
            💡 {MATERIAL_LABELS[material]}: step {profile.step_mm_range[0].toFixed(3)}–{profile.step_mm_range[1].toFixed(3)},
            gamma {profile.stone_gamma_range[0].toFixed(2)}–{profile.stone_gamma_range[1].toFixed(2)}
          </div>
          {profile.notes && (
            <div className="text-text-muted/80">{profile.notes}</div>
          )}
        </div>
      )}

      {/* Контекстная подсказка */}
      {activeHint && (
        <div className={`text-xs px-2 py-1 rounded border
          ${isIncompatible
            ? "bg-red-50 text-red-700 border-red-200"
            : "bg-yellow-50 text-yellow-700 border-yellow-200"
          }`}>
          {isIncompatible ? "🚫" : "⚠️"} {activeHint}
        </div>
      )}

      {/* Тост автокоррекций */}
      {toast && (
        <div className={`text-xs px-2 py-1.5 rounded border
          ${toastType === "error"
            ? "bg-red-50 text-red-700 border-red-200"
            : "bg-blue-50 text-blue-700 border-blue-200"
          }`}>
          {toastType === "error" ? "🚫" : "ℹ️"} {toast}
        </div>
      )}
    </div>
  );
}
