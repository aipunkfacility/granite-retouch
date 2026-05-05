/** Laser/Impact machine switcher */

interface Props {
  value: "laser" | "impact";
  onChange: (type: "laser" | "impact") => void;
}

export function MachineSwitch({ value, onChange }: Props) {
  return (
    <div className="flex gap-1 bg-bg-card rounded-lg p-1">
      <button
        onClick={() => onChange("laser")}
        className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-colors
          ${value === "laser" ? "bg-accent-blue text-white" : "text-text-secondary hover:text-text-primary"}`}
      >
        <i className="ri-flashlight-line mr-1" />
        Laser
      </button>
      <button
        onClick={() => onChange("impact")}
        className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-colors
          ${value === "impact" ? "bg-accent-blue text-white" : "text-text-secondary hover:text-text-primary"}`}
      >
        <i className="ri-contrast-2-line mr-1" />
        Impact
      </button>
    </div>
  );
}
