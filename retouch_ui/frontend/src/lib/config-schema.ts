/** Parameter range for UI slider */
export interface ParamRange {
  min: number;
  max: number;
  step: number;
  label: string;
  unit?: string;
}

/** Machine parameters (laser_standard / laser_80w / impact) */
export interface MachineParams {
  glow_size_min: ParamRange;
  glow_size_max: ParamRange;
  glow_opacity_min: ParamRange;
  glow_opacity_max: ParamRange;
  brightness: ParamRange;
  face_brightness_target_min: ParamRange;
  face_brightness_target_max: ParamRange;
  face_region_top: ParamRange;
  highlight_start: ParamRange;
}

/** Common processing parameters */
export interface ProcessingParams {
  blue_threshold: ParamRange;
  min_blue_ratio: ParamRange;
  fringe_radius: ParamRange;
}

/** Vignette parameters */
export interface VignetteParams {
  vertical_offset: ParamRange;
  vertical_diameter: ParamRange;
  blur_radius: ParamRange;
  headroom: ParamRange;
  horizontal_oversize: ParamRange;
}

/** Full config schema */
export interface ConfigSchema {
  processing: ProcessingParams & {
    laser_standard: MachineParams;
    laser_80w: MachineParams;
    impact: MachineParams;
  };
  vignette: VignetteParams;
}

/** Schema — used by params-panel.tsx to generate sliders */
export const CONFIG_SCHEMA: ConfigSchema = {
  processing: {
    blue_threshold: { min: 10, max: 80, step: 1, label: "Порог синего", unit: "" },
    min_blue_ratio: { min: 0, max: 1, step: 0.01, label: "Мин. доля синего", unit: "" },
    fringe_radius: { min: 0, max: 10, step: 1, label: "Радиус fringe-удаления", unit: "px" },
    laser_standard: {
      glow_size_min: { min: 5, max: 100, step: 1, label: "Glow: мин. размер", unit: "px" },
      glow_size_max: { min: 5, max: 100, step: 1, label: "Glow: макс. размер", unit: "px" },
      glow_opacity_min: { min: 10, max: 100, step: 1, label: "Glow: мин. непрозрачность", unit: "%" },
      glow_opacity_max: { min: 10, max: 100, step: 1, label: "Glow: макс. непрозрачность", unit: "%" },
      brightness: { min: 0.5, max: 1.5, step: 0.01, label: "Яркость", unit: "x" },
      face_brightness_target_min: { min: 100, max: 255, step: 1, label: "Цель яркости лица: мин", unit: "" },
      face_brightness_target_max: { min: 100, max: 255, step: 1, label: "Цель яркости лица: макс", unit: "" },
      face_region_top: { min: 0.2, max: 0.8, step: 0.01, label: "Зона лица (верх)", unit: "" },
      highlight_start: { min: 100, max: 250, step: 1, label: "Начало затухания коррекции", unit: "" },
    },
    laser_80w: {
      glow_size_min: { min: 5, max: 100, step: 1, label: "Glow: мин. размер", unit: "px" },
      glow_size_max: { min: 5, max: 100, step: 1, label: "Glow: макс. размер", unit: "px" },
      glow_opacity_min: { min: 10, max: 100, step: 1, label: "Glow: мин. непрозрачность", unit: "%" },
      glow_opacity_max: { min: 10, max: 100, step: 1, label: "Glow: макс. непрозрачность", unit: "%" },
      brightness: { min: 0.5, max: 1.5, step: 0.01, label: "Яркость", unit: "x" },
      face_brightness_target_min: { min: 100, max: 255, step: 1, label: "Цель яркости лица: мин", unit: "" },
      face_brightness_target_max: { min: 100, max: 255, step: 1, label: "Цель яркости лица: макс", unit: "" },
      face_region_top: { min: 0.2, max: 0.8, step: 0.01, label: "Зона лица (верх)", unit: "" },
      highlight_start: { min: 100, max: 250, step: 1, label: "Начало затухания коррекции", unit: "" },
    },
    impact: {
      glow_size_min: { min: 5, max: 100, step: 1, label: "Glow: мин. размер", unit: "px" },
      glow_size_max: { min: 5, max: 100, step: 1, label: "Glow: макс. размер", unit: "px" },
      glow_opacity_min: { min: 10, max: 100, step: 1, label: "Glow: мин. непрозрачность", unit: "%" },
      glow_opacity_max: { min: 10, max: 100, step: 1, label: "Glow: макс. непрозрачность", unit: "%" },
      brightness: { min: 0.5, max: 1.5, step: 0.01, label: "Яркость", unit: "x" },
      face_brightness_target_min: { min: 100, max: 255, step: 1, label: "Цель яркости лица: мин", unit: "" },
      face_brightness_target_max: { min: 100, max: 255, step: 1, label: "Цель яркости лица: макс", unit: "" },
      face_region_top: { min: 0.2, max: 0.8, step: 0.01, label: "Зона лица (верх)", unit: "" },
      highlight_start: { min: 100, max: 250, step: 1, label: "Начало затухания коррекции", unit: "" },
    },
  },
  vignette: {
    vertical_offset: { min: 0, max: 0.3, step: 0.01, label: "Вертикальное смещение", unit: "" },
    vertical_diameter: { min: 0.2, max: 0.8, step: 0.01, label: "Вертикальный диаметр", unit: "" },
    blur_radius: { min: 10, max: 120, step: 1, label: "Радиус размытия", unit: "px" },
    headroom: { min: 0.2, max: 1.0, step: 0.01, label: "Headroom", unit: "" },
    horizontal_oversize: { min: 0, max: 0.5, step: 0.01, label: "Горизонтальный оверсайз", unit: "" },
  },
};

/** Parameter groups for params-panel tabs */
export const PARAM_GROUPS = [
  { key: "common", label: "Общие", params: ["blue_threshold", "min_blue_ratio", "fringe_radius"] },
  { key: "laser_standard", label: "Laser 20-40W", params: Object.keys(CONFIG_SCHEMA.processing.laser_standard) },
  { key: "laser_80w", label: "Laser 80W+", params: Object.keys(CONFIG_SCHEMA.processing.laser_80w) },
  { key: "impact", label: "Impact", params: Object.keys(CONFIG_SCHEMA.processing.impact) },
  { key: "vignette", label: "Виньетка", params: Object.keys(CONFIG_SCHEMA.vignette) },
] as const;
