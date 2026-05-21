import { useState, useMemo } from "react";
import { CONFIG_SCHEMA, getMachineParams } from "../lib/config-schema";
import type { ParamSection, ParamToggle, ParamCheckbox, ParamDef } from "../lib/config-schema";
import type { MachineType, ConfigTree } from "../lib/types";
import { Slider } from "./slider";

/** Accordion group: collapsible section with param sliders/toggles and override badge */

interface Props {
  section: ParamSection;
  config: ConfigTree;
  machineType: MachineType;
  overriddenKeys?: Set<string>;
  defaultCollapsed?: boolean;
  onConfigChange: (path: string[], value: number | string) => void;
  onResetParam?: (key: string) => void;
}

function isParamToggle(param: ParamDef): param is ParamToggle {
  return "type" in param && param.type === "toggle";
}

function isParamCheckbox(param: ParamDef): param is ParamCheckbox {
  return "type" in param && param.type === "checkbox";
}

function isParamDef(val: unknown): val is ParamDef {
  return val != null && typeof val === "object" && ("label" in val || "type" in val);
}

function getPath(section: ParamSection, paramKey: string, machineType: MachineType): string[] {
  if (section.configPath) return [section.configPath, paramKey];
  const isCommonProcessing = paramKey in CONFIG_SCHEMA.processing;
  if (isCommonProcessing) return ["processing", paramKey];
  return ["processing", machineType, paramKey];
}

function getDef(section: ParamSection, paramKey: string, machineType: MachineType): ParamDef | null {
  if (section.configPath) {
    const schema = CONFIG_SCHEMA[section.configPath as keyof typeof CONFIG_SCHEMA];
    const val = (schema as unknown as Record<string, unknown>)?.[paramKey];
    return isParamDef(val) ? val : null;
  }
  const isCommonProcessing = paramKey in CONFIG_SCHEMA.processing;
  if (isCommonProcessing) {
    const val = CONFIG_SCHEMA.processing[paramKey as keyof typeof CONFIG_SCHEMA.processing];
    return isParamDef(val) ? val as unknown as ParamDef : null;
  }
  const machineParams = getMachineParams(machineType);
  const val = machineParams[paramKey];
  return isParamDef(val) ? val : null;
}

function getValue(config: ConfigTree, path: string[]): number | string {
  let obj: unknown = config;
  for (const key of path) obj = (obj as Record<string, unknown>)?.[key];
  if (typeof obj === "string") return obj;
  return typeof obj === "number" ? obj : 0;
}

export function ParamGroup({
  section,
  config,
  machineType,
  overriddenKeys,
  defaultCollapsed = true,
  onConfigChange,
  onResetParam,
}: Props) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  const overriddenCount = useMemo(() => {
    if (!overriddenKeys) return 0;
    let count = 0;
    for (const paramKey of section.params) {
      const pathKey = getPath(section, paramKey, machineType).join(".");
      if (overriddenKeys.has(pathKey)) count++;
    }
    return count;
  }, [section, machineType, overriddenKeys]);

  return (
    <div className="bg-bg-card rounded-lg shadow-sm overflow-hidden">
      <button
        onClick={() => setCollapsed((prev) => !prev)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs font-heading font-semibold uppercase tracking-wide text-text-secondary hover:bg-bg-hover transition-colors duration-200"
        aria-expanded={!collapsed}
      >
        <i className={`${section.icon} text-sm text-text-muted`} />
        <span className="flex-1 text-left">{section.label}</span>
        {overriddenCount > 0 && (
          <span className="text-[10px] font-mono text-accent-blue">{overriddenCount} изменены</span>
        )}
        {overriddenCount === 0 && (
          <span className="text-[10px] font-mono text-text-muted">по умолчанию</span>
        )}
        <i className={`ri-arrow-${collapsed ? "down" : "up"}-s-line text-xs text-text-muted transition-transform duration-200 ${collapsed ? "" : "rotate-180"}`} />
      </button>

      <div
        className={`transition-all duration-250 overflow-hidden${isVignetteDisabled ? " pointer-events-none" : ""} ${collapsed ? "max-h-0 opacity-0" : "max-h-[50vh] opacity-100"}`}
      >
        <div className="px-3 pb-3 space-y-3">
          {section.params.map((paramKey) => {
            const def = getDef(section, paramKey, machineType);
            if (!def) return null;
            const path = getPath(section, paramKey, machineType);
            const pathKey = path.join(".");
            const isOverridden = overriddenKeys?.has(pathKey) ?? false;

            if (isParamToggle(def)) {
              const value = String(getValue(config, path));
              return (
                <div key={pathKey} className="space-y-1">
                  <label className="text-sm text-text-secondary">{def.label}</label>
                  <div className="flex gap-1">
                    {def.options.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => onConfigChange(path, opt.value)}
                        className={`px-3 py-1 text-sm rounded-lg transition-colors duration-200 ${
                          value === opt.value
                            ? "bg-accent-blue text-white"
                            : "bg-bg-input text-text-muted hover:bg-bg-hover"
                        }`}
                        aria-pressed={value === opt.value}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>
              );
            }

            if (isParamCheckbox(def)) {
              const raw = getValue(config, path);
              const checked = raw === true || raw === 1;
              return (
                <label key={pathKey} className="flex items-center gap-2 text-sm text-text-primary cursor-pointer">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => onConfigChange(path, e.target.checked ? 1 : 0)}
                    className="accent-accent-blue w-4 h-4"
                  />
                  {def.label}
                </label>
              );
            }

            const numVal = getValue(config, path);
            return (
              <Slider
                key={pathKey}
                label={def.label}
                value={typeof numVal === "number" ? numVal : parseFloat(String(numVal)) || 0}
                min={def.min}
                max={def.max}
                step={def.step}
                unit={def.unit}
                overridden={isOverridden}
                onChange={(v) => onConfigChange(path, v)}
                onReset={onResetParam ? () => onResetParam(pathKey) : undefined}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
