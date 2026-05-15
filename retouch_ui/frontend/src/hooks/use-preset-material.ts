/** Единый хук для пресета + материала + baseline.
 *
 * Управляет состоянием:
 *   - selectedPreset — выбранный пресет
 *   - presetBaseline — слепок параметров пресета
 *   - overriddenKeys — параметры, изменённые вручную
 *   - material — текущий материал
 *   - materialChanges — автокоррекции
 *   - validationWarnings — предупреждения
 *   - activeHint — контекстная подсказка
 */

import { useState, useCallback, useEffect } from "react";
import { fetchMaterialApply, fetchPresets } from "../lib/api";
import { usePresetCatalog } from "./use-preset-catalog";
import { useMaterialProfiles } from "./use-material-profiles";
import type { MachineType, MaterialType, ConfigTree, MaterialChange, MaterialProfile, PresetCatalogEntry, CatalogGroup } from "../lib/types";

export interface PresetMaterialState {
  selectedPreset: string | null;
  presetBaseline: ConfigTree | null;
  overriddenKeys: Set<string>;
  machineType: MachineType;
  material: MaterialType;
  materialChanges: MaterialChange[];
  validationWarnings: string[];
  activeHint: string | null;
}

export interface UsePresetMaterialReturn extends PresetMaterialState {
  catalog: Record<string, PresetCatalogEntry>;
  groups: CatalogGroup[];
  profiles: Record<string, MaterialProfile>;
  catalogLoading: boolean;
  profilesLoading: boolean;
  presetsCache: Record<string, ConfigTree>;
  presetsLoaded: boolean;
  presetsError: string | null;
  selectPreset: (presetKey: string, presetConfig: ConfigTree) => void;
  switchModule: (presetKey: string, presetConfig: ConfigTree) => void;
  selectMaterial: (material: MaterialType, currentConfig?: ConfigTree) => Promise<{ success: boolean; validationWarnings: string[] }>;
  resetParam: (key: string) => ConfigTree | null;
  markOverridden: (key: string) => void;
  materialError: string | null;
}

export function usePresetMaterial(): UsePresetMaterialReturn {
  const { catalog, groups, loading: catalogLoading } = usePresetCatalog();
  const { profiles, loading: profilesLoading } = useMaterialProfiles();

  const [state, setState] = useState<PresetMaterialState>({
    selectedPreset: null,
    presetBaseline: null,
    overriddenKeys: new Set(),
    machineType: "laser_standard",
    material: "granite",
    materialChanges: [],
    validationWarnings: [],
    activeHint: null,
  });

  const [presetsCache, setPresetsCache] = useState<Record<string, ConfigTree>>({});
  const [presetsLoaded, setPresetsLoaded] = useState(false);
  const [presetsError, setPresetsError] = useState<string | null>(null);
  const [materialError, setMaterialError] = useState<string | null>(null);

  useEffect(() => {
    if (presetsLoaded) return;
    fetchPresets()
      .then(data => {
        setPresetsError(null);
        const cache: Record<string, ConfigTree> = {};
        for (const p of data.presets) cache[p.name] = p.config;
        setPresetsCache(cache);
        setPresetsLoaded(true);
      })
      .catch((err) => {
        setPresetsError(err instanceof Error ? err.message : "Ошибка загрузки пресетов");
      });
  }, [presetsLoaded]);

  const selectPreset = useCallback((presetKey: string, presetConfig: ConfigTree) => {
    setState((prev) => {
      // Определить machine_type из каталога
      const entry = catalog[presetKey];
      const mt = (entry?.machine_type || prev.machineType) as MachineType;
      const mat = (presetConfig as Record<string, unknown>)?.stone
        ? ((presetConfig as Record<string, Record<string, unknown>>).stone?.material as MaterialType) || prev.material
        : prev.material;

      return {
        ...prev,
        selectedPreset: presetKey,
        presetBaseline: presetConfig,
        overriddenKeys: new Set(),
        machineType: mt,
        material: mat,
        // Пересчитать hint
        activeHint: getActiveHint(presetKey, mat, mt, catalog, profiles),
      };
    });
  }, [catalog, profiles]);

  const switchModule = useCallback((presetKey: string, presetConfig: ConfigTree) => {
    // Переключение модуля = выбор другого пресета в комби-группе
    selectPreset(presetKey, presetConfig);
  }, [selectPreset]);

  const selectMaterial = useCallback(async (
    material: MaterialType,
    currentConfig?: ConfigTree,
  ): Promise<{ success: boolean; validationWarnings: string[] }> => {
    try {
      const result = await fetchMaterialApply(material, state.machineType, currentConfig);

      // Проверяем ERROR — блокируем выбор
      const hasError = result.validation_warnings.some(w => w.startsWith("ERROR:"));
      if (hasError) {
        return { success: false, validationWarnings: result.validation_warnings };
      }

      setState((prev) => ({
        ...prev,
        material,
        materialChanges: result.changes,
        validationWarnings: result.validation_warnings,
        activeHint: getActiveHint(prev.selectedPreset, material, prev.machineType, catalog, profiles),
      }));
      return { success: true, validationWarnings: result.validation_warnings };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Ошибка применения материала";
      setMaterialError(msg);
      return { success: false, validationWarnings: [] };
    }
  }, [state.machineType, catalog, profiles]);

  const resetParam = useCallback((key: string): ConfigTree | null => {
    if (!state.presetBaseline) return null;

    setState((prev) => {
      const newOverridden = new Set(prev.overriddenKeys);
      newOverridden.delete(key);
      return { ...prev, overriddenKeys: newOverridden };
    });

    return state.presetBaseline;
  }, [state.presetBaseline]);

  const markOverridden = useCallback((key: string) => {
    setState((prev) => {
      const newOverridden = new Set(prev.overriddenKeys);
      newOverridden.add(key);
      return { ...prev, overriddenKeys: newOverridden };
    });
  }, []);

  return {
    ...state,
    catalog,
    groups,
    profiles,
    catalogLoading,
    profilesLoading,
    presetsCache,
    presetsLoaded,
    presetsError,
    selectPreset,
    switchModule,
    selectMaterial,
    resetParam,
    markOverridden,
    materialError,
  };
}

/** Вычислить контекстную подсказку */
function getActiveHint(
  preset: string | null,
  material: MaterialType,
  machineType: MachineType,
  catalog: Record<string, PresetCatalogEntry>,
  profiles: Record<string, MaterialProfile>,
): string | null {
  // 1. Preset alert (самый высокий приоритет)
  if (preset) {
    const presetEntry = catalog[preset];
    if (presetEntry?.alert) return presetEntry.alert;
  }

  // 2. Material hint для текущего machine_type
  const profile = profiles[material];
  if (profile?.hints?.[machineType]) return profile.hints[machineType]!;

  // 3. Material notes
  if (profile?.notes) return profile.notes;

  return null;
}
