/** Machine type switcher: laser_standard / laser_80w / impact */

import type { MachineType } from "../lib/types";

interface Props {
  value: MachineType;
  onChange: (type: MachineType) => void;
}

const OPTIONS: { key: MachineType; label: string; icon: string }[] = [
  { key: "laser_standard", label: "Laser 20-40W", icon: "ri-flashlight-line" },
  { key: "laser_80w", label: "Laser 80W+", icon: "ri-flashlight-fill" },
  { key: "impact", label: "Impact", icon: "ri-contrast-2-line" },
];

export function MachineSwitch({ value, onChange }: Props) {
  return (
    <div className="flex gap-1 bg-bg-card rounded-lg p-1">
      {OPTIONS.map(({ key, label, icon }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`px-3 py-1.5 rounded-md text-sm font-semibold transition-colors
            ${value === key ? "bg-accent-blue text-white" : "text-text-secondary hover:text-text-primary"}`}
        >
          <i className={`${icon} mr-1`} />
          {label}
        </button>
      ))}
    </div>
  );
}
