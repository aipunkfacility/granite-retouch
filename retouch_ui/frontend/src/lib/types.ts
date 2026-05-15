/** Shared type definitions for the granite-retouch Web UI. */

/** Machine type — matches backend schema regex: ^(laser_standard|laser_80w|impact)$ */
export type MachineType = "laser_standard" | "laser_80w" | "impact";

/** Material type — matches backend StoneConfig.material pattern (v4) */
export type MaterialType = "granite" | "marble" | "gabbro" | "basalt" | "acrylic";

/** @deprecated Use MaterialType instead. Alias for backward compatibility. */
export type StoneType = MaterialType;

/** Face oval params — matches backend FaceOvalParams schema (E.1) */
export interface FaceOvalParams {
  cx: number;    // центр X (0–1)
  cy: number;    // центр Y (0–1)
  rx: number;    // радиус X (0–1)
  ry: number;    // радиус Y (0–1)
  source: "heuristic" | "manual" | "auto" | "heuristic_legacy";
}

/** Recursive config tree — backend returns nested JSON with numeric leaves.
 *
 * Replaces Record<string, any> throughout the frontend to enable
 * TypeScript checking on config access paths.
 */
export type ConfigValue = number | string | ConfigTree;
export interface ConfigTree {
  [key: string]: ConfigValue;
}

/** Preset catalog entry — matches backend PRESET_CATALOG item */
export interface PresetCatalogEntry {
  label: string;
  category: "technology" | "machine";
  machine_type: MachineType;
  brand?: string;
  combo_group?: string;
  alert?: string;
}

/** Material profile — matches backend MATERIAL_PROFILES item */
export interface MaterialProfile {
  step_mm_range: [number, number];
  stone_gamma_range: [number, number];
  shadow_floor: number;
  white_ceiling_offset: number;
  notes?: string;
  hints?: Partial<Record<MachineType, string>>;
  export_mode_override?: string;
  dither_method_override?: string;
  incompatible_machine_types?: MachineType[];
}

/** Material auto-correction change */
export interface MaterialChange {
  param: string;
  old: number | string;
  new: number | string;
  reason?: string;
}

/** Result of POST /api/material/apply */
export interface MaterialApplyResult {
  config_patch: ConfigTree;
  changes: MaterialChange[];
  validation_warnings: string[];
  active_hint: string | null;
}

/** Grouped catalog entry for MachineSelector */
export interface CatalogGroup {
  title: string;
  type: "combo" | "brand" | "technology";
  presets: { key: string; entry: PresetCatalogEntry }[];
}

/** Type guard for ConfigTree — checks for plain object.
 *  Filters out null, arrays, and class instances (Date, Map, Set, Error, etc.)
 *  by verifying prototype is Object.prototype or null (Object.create(null)).
 *  Used as runtime guard for ConfigTree in place of unsafe `as ConfigTree` casts. */
export function isConfigTree(val: unknown): val is ConfigTree {
  return val !== null
    && typeof val === "object"
    && !Array.isArray(val)
    && (Object.getPrototypeOf(val) === Object.prototype
      || Object.getPrototypeOf(val) === null);
}
