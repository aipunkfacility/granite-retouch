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
