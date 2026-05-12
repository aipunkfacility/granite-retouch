/** Parameter range for UI slider */
export interface ParamRange {
  min: number;
  max: number;
  step: number;
  label: string;
  unit?: string;
}

/** Toggle parameter (on/off or option switch) */
export interface ParamToggle {
  type: "toggle";
  options: { value: number; label: string }[];
  label: string;
}

/** Union type for any parameter definition */
export type ParamDef = ParamRange | ParamToggle;

/** Machine parameters (laser_standard / laser_80w / impact) */
export interface MachineParams {
  glow_size_min: ParamRange;
  glow_size_max: ParamRange;
  glow_opacity_min: ParamRange;
  glow_opacity_max: ParamRange;
  stone_gamma: ParamRange;  // FIX-11: заменён brightness → stone_gamma (SOP 5.1)
  face_brightness_target_min: ParamRange;
  face_brightness_target_max: ParamRange;
  face_region_top: ParamRange;
  highlight_start: ParamRange;
  white_ceiling: ParamRange;
  glow_style: ParamToggle;  // 0=outer, 1=inner — сегментный контрол
  unsharp_threshold: ParamRange;  // Advanced — порог резкости
}

/** Impact-specific extra parameters */
export interface ImpactParams {
  shadow_noise_min: ParamRange;
  shadow_noise_max: ParamRange;
  shadow_noise_threshold: ParamRange;
  shadow_floor: ParamRange;
}

/** Common processing parameters */
export interface ProcessingParams {
  blue_threshold: ParamRange;
  min_blue_ratio: ParamRange;
  fringe_radius: ParamRange;
  legacy_step_order: ParamRange;  // 0=false, 1=true — toggle [HIDDEN]
  min_resolution: ParamRange;
  result_min_black_ratio: ParamRange;
  mask_soft_sigma: ParamRange;           // НОВОЕ — Advanced
  contour_smooth_epsilon: ParamRange;    // НОВОЕ — Advanced
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
    impact: MachineParams & ImpactParams;
  };
  vignette: VignetteParams;
}

/** Parameters hidden by default — shown only in Advanced Mode */
export const ADVANCED_PARAMS = new Set([
  "blue_threshold",
  "min_blue_ratio",
  "fringe_radius",
  "min_resolution",
  "result_min_black_ratio",
  "face_region_top",
  "highlight_start",
  "unsharp_threshold",
  "mask_soft_sigma",
  "contour_smooth_epsilon",
]);

/** Parameters removed from UI entirely (dev-only or deprecated) */
export const HIDDEN_PARAMS = new Set([
  "legacy_step_order",  // dev-rollback, мёртвый параметр
]);

/** Schema — used by params-panel.tsx to generate sliders */
export const CONFIG_SCHEMA: ConfigSchema = {
  processing: {
    blue_threshold: { min: 10, max: 80, step: 1, label: "Порог синего", unit: "" },
    min_blue_ratio: { min: 0, max: 1, step: 0.01, label: "Мин. доля синего", unit: "" },
    fringe_radius: { min: 0, max: 10, step: 1, label: "Радиус fringe-удаления", unit: "px" },
    legacy_step_order: { min: 0, max: 1, step: 1, label: "Старый порядок шагов", unit: "(0/1)" },
    min_resolution: { min: 256, max: 1024, step: 64, label: "Мин. разрешение", unit: "px" },
    result_min_black_ratio: { min: 0, max: 0.5, step: 0.01, label: "Мин. доля чёрного", unit: "" },
    mask_soft_sigma: { min: 0, max: 5, step: 0.1, label: "Мягкость краёв маски", unit: "σ" },
    contour_smooth_epsilon: { min: 0.001, max: 0.01, step: 0.001, label: "Сглаживание контура", unit: "" },
    laser_standard: {
      glow_size_min: { min: 5, max: 100, step: 1, label: "Glow: мин. размер", unit: "px" },
      glow_size_max: { min: 5, max: 100, step: 1, label: "Glow: макс. размер", unit: "px" },
      glow_opacity_min: { min: 10, max: 100, step: 1, label: "Glow: мин. непрозрачность", unit: "%" },
      glow_opacity_max: { min: 10, max: 100, step: 1, label: "Glow: макс. непрозрачность", unit: "%" },
      stone_gamma: { min: 0.5, max: 1.5, step: 0.01, label: "Гамма камня", unit: "" },
      face_brightness_target_min: { min: 100, max: 255, step: 1, label: "Цель яркости лица: мин", unit: "" },
      face_brightness_target_max: { min: 100, max: 255, step: 1, label: "Цель яркости лица: макс", unit: "" },
      face_region_top: { min: 0.2, max: 0.8, step: 0.01, label: "Зона лица (верх)", unit: "" },
      highlight_start: { min: 100, max: 250, step: 1, label: "Начало затухания коррекции", unit: "" },
      white_ceiling: { min: 200, max: 255, step: 1, label: "Потолок белизны", unit: "" },
      glow_style: { type: "toggle", options: [{ value: 0, label: "Outer" }, { value: 1, label: "Inner" }], label: "Стиль Glow" },
      unsharp_threshold: { min: 0, max: 20, step: 1, label: "Порог резкости", unit: "" },
    },
    laser_80w: {
      glow_size_min: { min: 5, max: 100, step: 1, label: "Glow: мин. размер", unit: "px" },
      glow_size_max: { min: 5, max: 100, step: 1, label: "Glow: макс. размер", unit: "px" },
      glow_opacity_min: { min: 10, max: 100, step: 1, label: "Glow: мин. непрозрачность", unit: "%" },
      glow_opacity_max: { min: 10, max: 100, step: 1, label: "Glow: макс. непрозрачность", unit: "%" },
      stone_gamma: { min: 0.5, max: 1.5, step: 0.01, label: "Гамма камня", unit: "" },
      face_brightness_target_min: { min: 100, max: 255, step: 1, label: "Цель яркости лица: мин", unit: "" },
      face_brightness_target_max: { min: 100, max: 255, step: 1, label: "Цель яркости лица: макс", unit: "" },
      face_region_top: { min: 0.2, max: 0.8, step: 0.01, label: "Зона лица (верх)", unit: "" },
      highlight_start: { min: 100, max: 250, step: 1, label: "Начало затухания коррекции", unit: "" },
      white_ceiling: { min: 200, max: 255, step: 1, label: "Потолок белизны", unit: "" },
      glow_style: { type: "toggle", options: [{ value: 0, label: "Outer" }, { value: 1, label: "Inner" }], label: "Стиль Glow" },
      unsharp_threshold: { min: 0, max: 20, step: 1, label: "Порог резкости", unit: "" },
    },
    impact: {
      glow_size_min: { min: 5, max: 100, step: 1, label: "Glow: мин. размер", unit: "px" },
      glow_size_max: { min: 5, max: 100, step: 1, label: "Glow: макс. размер", unit: "px" },
      glow_opacity_min: { min: 10, max: 100, step: 1, label: "Glow: мин. непрозрачность", unit: "%" },
      glow_opacity_max: { min: 10, max: 100, step: 1, label: "Glow: макс. непрозрачность", unit: "%" },
      stone_gamma: { min: 0.5, max: 1.5, step: 0.01, label: "Гамма камня", unit: "" },
      face_brightness_target_min: { min: 100, max: 255, step: 1, label: "Цель яркости лица: мин", unit: "" },
      face_brightness_target_max: { min: 100, max: 255, step: 1, label: "Цель яркости лица: макс", unit: "" },
      face_region_top: { min: 0.2, max: 0.8, step: 0.01, label: "Зона лица (верх)", unit: "" },
      highlight_start: { min: 100, max: 250, step: 1, label: "Начало затухания коррекции", unit: "" },
      white_ceiling: { min: 200, max: 255, step: 1, label: "Потолок белизны", unit: "" },
      glow_style: { type: "toggle", options: [{ value: 0, label: "Outer" }, { value: 1, label: "Inner" }], label: "Стиль Glow" },
      unsharp_threshold: { min: 0, max: 20, step: 1, label: "Порог резкости", unit: "" },
      shadow_noise_min: { min: 0, max: 30, step: 1, label: "Шум теней: мин", unit: "" },
      shadow_noise_max: { min: 0, max: 30, step: 1, label: "Шум теней: макс", unit: "" },
      shadow_noise_threshold: { min: 10, max: 80, step: 1, label: "Порог шума теней", unit: "" },
      shadow_floor: { min: 0, max: 30, step: 1, label: "Тень: мин. яркость", unit: "" },
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
  { key: "common", label: "Общие", params: ["blue_threshold", "min_blue_ratio", "fringe_radius", "legacy_step_order", "min_resolution", "result_min_black_ratio", "mask_soft_sigma", "contour_smooth_epsilon"] },
  { key: "laser_standard", label: "Laser 20-40W", params: Object.keys(CONFIG_SCHEMA.processing.laser_standard) },
  { key: "laser_80w", label: "Laser 80W+", params: Object.keys(CONFIG_SCHEMA.processing.laser_80w) },
  { key: "impact", label: "Impact", params: Object.keys(CONFIG_SCHEMA.processing.impact) },
  { key: "vignette", label: "Виньетка", params: Object.keys(CONFIG_SCHEMA.vignette) },
] as const;
