import type { MachineType } from "./types";

export interface MachineTheme {
  bg: string;
  border: string;
  dot: string;
  icon: string;
  label: string;
}

export const MACHINE_THEME: Record<MachineType, MachineTheme> = {
  impact: { bg: "bg-orange-50", border: "border-orange-200", dot: "bg-orange-400", icon: "ri-contrast-2-line", label: "Ударный" },
  laser_standard: { bg: "bg-green-50", border: "border-green-200", dot: "bg-green-400", icon: "ri-flashlight-line", label: "CO2 40W" },
  laser_80w: { bg: "bg-red-50", border: "border-red-200", dot: "bg-red-400", icon: "ri-flashlight-fill", label: "Диод 80W" },
};
