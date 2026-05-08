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

/** Preview params — matches backend PreviewParams schema (D.4) */
export interface PreviewParams {
  brightness?: number | null;
  glow_size?: number | null;
  glow_opacity?: number | null;
  face_oval?: FaceOvalParams | null;
  stone_type?: string | null;
  step_mm?: number | null;
  highlight_start?: number | null;
  face_region_top?: number | null;
  legacy_step_order?: boolean | null;
}
