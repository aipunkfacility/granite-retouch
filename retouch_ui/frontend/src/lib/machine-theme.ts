import type { MachineType } from "./types";

export interface MachineTheme {
  bg: string;
  border: string;
  dot: string;
  icon: string;
  label: string;
}

export const MACHINE_THEME: Record<MachineType, MachineTheme> = {
  impact: { bg: "bg-accent-orange/10", border: "border-accent-orange/30", dot: "bg-accent-orange", icon: "ri-contrast-2-line", label: "Ударный" },
  laser_standard: { bg: "bg-accent-green/10", border: "border-accent-green/30", dot: "bg-accent-green", icon: "ri-flashlight-line", label: "CO2 40W" },
  laser_80w: { bg: "bg-accent-red/10", border: "border-accent-red/30", dot: "bg-accent-red", icon: "ri-flashlight-fill", label: "Диод 80W" },
};
