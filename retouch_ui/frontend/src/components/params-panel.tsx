import { CONFIG_SCHEMA, PARAM_GROUPS } from "../lib/config-schema";
import type { ParamRange, MachineParams } from "../lib/config-schema";
import { useState } from "react";

interface Props {
  machineType: "laser" | "impact";
  config: Record<string, any>;
  onConfigChange: (path: string[], value: number) => void;
}

export function ParamsPanel({ machineType, config, onConfigChange }: Props) {
  const [activeTab, setActiveTab] = useState<string>("common");

  const renderSlider = (path: string[], param: ParamRange, value: number) => (
    <div key={path.join(".")} className="space-y-1">
      <div className="flex justify-between text-sm">
        <label className="text-text-secondary">{param.label}</label>
        <span className="text-text-muted font-mono text-xs">
          {value}
          {param.unit ? ` ${param.unit}` : ""}
        </span>
      </div>
      <input
        type="range"
        min={param.min}
        max={param.max}
        step={param.step}
        value={value}
        onChange={(e) => onConfigChange(path, parseFloat(e.target.value))}
        className="w-full"
      />
    </div>
  );

  const getParamRange = (groupKey: string, paramKey: string): ParamRange | null => {
    if (groupKey === "common") {
      return CONFIG_SCHEMA.processing[paramKey as keyof typeof CONFIG_SCHEMA.processing] as ParamRange | null;
    }
    if (groupKey === "vignette") {
      return CONFIG_SCHEMA.vignette[paramKey as keyof typeof CONFIG_SCHEMA.vignette] as ParamRange | null;
    }
    if (groupKey === "laser" || groupKey === "impact") {
      const machine = CONFIG_SCHEMA.processing[groupKey] as MachineParams | undefined;
      return machine?.[paramKey as keyof MachineParams] ?? null;
    }
    return null;
  };

  const getValue = (path: string[]): number => {
    let obj: unknown = config;
    for (const key of path) obj = (obj as Record<string, unknown>)?.[key];
    return typeof obj === "number" ? obj : 0;
  };

  // Show only relevant tabs based on machineType
  const visibleTabs = PARAM_GROUPS.filter(
    (g) => g.key === "common" || g.key === machineType || g.key === "vignette",
  );

  // If activeTab is not in visibleTabs, switch to "common"
  const effectiveTab = visibleTabs.some((g) => g.key === activeTab) ? activeTab : "common";

  return (
    <div className="space-y-4">
      <h3 className="font-heading font-semibold text-text-primary text-sm">Параметры</h3>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {visibleTabs.map((g) => (
          <button
            key={g.key}
            onClick={() => setActiveTab(g.key)}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors
              ${
                effectiveTab === g.key
                  ? "border-accent-blue text-accent-blue"
                  : "border-transparent text-text-muted hover:text-text-secondary"
              }`}
          >
            {g.label}
          </button>
        ))}
      </div>

      {/* Sliders */}
      <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
        {visibleTabs
          .filter((g) => g.key === effectiveTab)
          .map((g) =>
            g.params.map((paramKey) => {
              const range = getParamRange(g.key, paramKey);
              if (!range) return null;
              const path =
                g.key === "common"
                  ? ["processing", paramKey]
                  : g.key === "vignette"
                    ? ["vignette", paramKey]
                    : ["processing", g.key, paramKey];
              return renderSlider(path, range, getValue(path));
            }),
          )}
      </div>
    </div>
  );
}
