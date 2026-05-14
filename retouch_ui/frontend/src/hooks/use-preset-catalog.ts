/** Хук для загрузки и кэширования PRESET_CATALOG.
 * Вызывает GET /api/presets/catalog один раз при монтировании.
 */

import { useState, useEffect } from "react";
import { fetchPresetCatalog } from "../lib/api";
import type { PresetCatalogEntry, CatalogGroup } from "../lib/types";

interface UsePresetCatalogReturn {
  catalog: Record<string, PresetCatalogEntry>;
  groups: CatalogGroup[];
  loading: boolean;
  error: string | null;
}

/** Бренд-label маппинг для группировки */
const BRAND_LABELS: Record<string, string> = {
  sauno: "САУНО",
  mirtels: "Mirtels",
  stanzone: "Stanzone",
  stonegraf: "STONE-ГРАФ",
};

/** Группировка каталога по combo_group / brand / category */
function groupCatalog(catalog: Record<string, PresetCatalogEntry>): CatalogGroup[] {
  const comboGroups: Map<string, CatalogGroup> = new Map();
  const brandGroups: Map<string, CatalogGroup> = new Map();
  let techGroup: CatalogGroup | null = null;

  for (const [key, entry] of Object.entries(catalog)) {
    // 1. Пресеты с combo_group → отдельные группы
    if (entry.combo_group) {
      if (!comboGroups.has(entry.combo_group)) {
        comboGroups.set(entry.combo_group, {
          title: BRAND_LABELS[entry.combo_group] || entry.combo_group,
          type: "combo",
          presets: [],
        });
      }
      comboGroups.get(entry.combo_group)!.presets.push({ key, entry });
    }
    // 2. Технологические пресеты
    else if (entry.category === "technology") {
      if (!techGroup) {
        techGroup = { title: "По технологии", type: "technology", presets: [] };
      }
      techGroup.presets.push({ key, entry });
    }
    // 3. Пресеты по бренду
    else if (entry.brand) {
      const brand = entry.brand;
      if (!brandGroups.has(brand)) {
        brandGroups.set(brand, {
          title: BRAND_LABELS[brand] || brand,
          type: "brand",
          presets: [],
        });
      }
      brandGroups.get(brand)!.presets.push({ key, entry });
    }
  }

  // Собираем в порядке: комби-группы → бренды → технологии
  const result: CatalogGroup[] = [
    ...comboGroups.values(),
    ...brandGroups.values(),
  ];
  if (techGroup) {
    result.push(techGroup);
  }
  return result;
}

let _cachedCatalog: Record<string, PresetCatalogEntry> | null = null;
let _cachedGroups: CatalogGroup[] | null = null;

export function usePresetCatalog(): UsePresetCatalogReturn {
  const [catalog, setCatalog] = useState<Record<string, PresetCatalogEntry>>(_cachedCatalog || {});
  const [groups, setGroups] = useState<CatalogGroup[]>(_cachedGroups || []);
  const [loading, setLoading] = useState(!_cachedCatalog);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (_cachedCatalog) return; // Уже загружен

    fetchPresetCatalog()
      .then((data) => {
        _cachedCatalog = data.catalog;
        _cachedGroups = groupCatalog(data.catalog);
        setCatalog(data.catalog);
        setGroups(_cachedGroups);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Ошибка загрузки каталога");
        setLoading(false);
      });
  }, []);

  return { catalog, groups, loading, error };
}
