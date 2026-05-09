/** Shared type definitions for the granite-retouch Web UI. */

/** Machine type — matches backend schema regex: ^(laser_standard|laser_80w|impact)$ */
export type MachineType = "laser_standard" | "laser_80w" | "impact";

/** Face oval params — matches backend FaceOvalParams schema (E.1) */
export interface FaceOvalParams {
  cx: number;    // центр X (0–1)
  cy: number;    // центр Y (0–1)
  rx: number;    // радиус X (0–1)
  ry: number;    // радиус Y (0–1)
  source: "heuristic" | "manual" | "auto" | "heuristic_legacy";
}
