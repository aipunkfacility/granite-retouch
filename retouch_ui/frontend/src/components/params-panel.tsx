import { CONFIG_SCHEMA, PARAM_GROUPS, ADVANCED_PARAMS, HIDDEN_PARAMS } from "../lib/config-schema";
import type { ParamRange, ParamToggle, ParamDef } from "../lib/config-schema";
import type { MachineType, ConfigTree } from "../lib/types";
import { useState } from "react";

interface Props {
  machineType: MachineType;
  config: ConfigTree;
  onConfigChange: (path: string[], value: number | string) => void;
  vignetteOverlayEnabled: boolean;
  onVignetteOverlayToggle: (enabled: boolean) => void;
  faceOvalOverlayEnabled: boolean;
  onFaceOvalOverlayToggle: (enabled: boolean) => void;
  faceOvalPinned: boolean;
  onFaceOvalPinToggle: () => void;
}

/** Type guard for ParamToggle */
function isParamToggle(param: ParamDef): param is ParamToggle {
  return "type" in param && param.type === "toggle";
}

/** Type guard for ParamDef — checks if value looks like a valid param definition */
function isParamDef(val: unknown): val is ParamDef {
  return val != null && typeof val === "object" && ("label" in val || "type" in val);
}

export function ParamsPanel({
  machineType,
  config,
  onConfigChange,
  vignetteOverlayEnabled,
  onVignetteOverlayToggle,
  faceOvalOverlayEnabled,
  onFaceOvalOverlayToggle,
  faceOvalPinned,
  onFaceOvalPinToggle,
}: Props) {
  const [activeTab, setActiveTab] = useState<string>("common");
  const [showAdvanced, setShowAdvanced] = useState(false);

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

  const renderToggle = (path: string[], param: ParamToggle, value: string) => (
    <div key={path.join(".")} className="space-y-1">
      <label className="text-sm text-text-secondary">{param.label}</label>
      <div className="flex gap-1">
        {param.options.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onConfigChange(path, opt.value)}
            className={`px-3 py-1 text-sm rounded-md transition-colors
              ${
                value === opt.value
                  ? "bg-accent-blue text-white"
                  : "bg-bg-input text-text-muted hover:bg-bg-hover"
              }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );

  const getParamDef = (groupKey: string, paramKey: string): ParamDef | null => {
    if (groupKey === "common") {
      const val = CONFIG_SCHEMA.processing[paramKey as keyof typeof CONFIG_SCHEMA.processing];
      return isParamDef(val) ? val : null;
    }
    if (groupKey === "vignette") {
      const val = CONFIG_SCHEMA.vignette[paramKey as keyof typeof CONFIG_SCHEMA.vignette];
      return isParamDef(val) ? val : null;
    }
    if (groupKey === "laser_standard" || groupKey === "laser_80w" || groupKey === "impact") {
      const machine = CONFIG_SCHEMA.processing[groupKey] as Record<string, ParamDef> | undefined;
      return machine?.[paramKey] ?? null;
    }
    return null;
  };

  const getValue = (path: string[]): number | string => {
    let obj: unknown = config;
    for (const key of path) obj = (obj as Record<string, unknown>)?.[key];
    if (typeof obj === "string") return obj;
    return typeof obj === "number" ? obj : 0;
  };

  // Show only relevant tabs based on machineType
  const visibleTabs = PARAM_GROUPS.filter(
    (g) => g.key === "common" || g.key === machineType || g.key === "vignette",
  );

  // If activeTab is not in visibleTabs, switch to "common"
  const effectiveTab = visibleTabs.some((g) => g.key === activeTab) ? activeTab : "common";

  // Filter params by Advanced Mode and Hidden
  const shouldShowParam = (paramKey: string): boolean => {
    if (HIDDEN_PARAMS.has(paramKey)) return false;
    if (!showAdvanced && ADVANCED_PARAMS.has(paramKey)) return false;
    return true;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-heading font-semibold text-text-primary text-sm">Параметры</h3>
        <label className="flex items-center gap-2 text-xs text-text-muted cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showAdvanced}
            onChange={(e) => setShowAdvanced(e.target.checked)}
            className="accent-accent-blue"
          />
          <i className="ri-settings-3-line" />
          Advanced
        </label>
      </div>

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

      {/* Vignette overlay toggle — shown only on vignette tab */}
      {effectiveTab === "vignette" && (
        <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer select-none">
          <input
            type="checkbox"
            checked={vignetteOverlayEnabled}
            onChange={(e) => onVignetteOverlayToggle(e.target.checked)}
            className="accent-accent-blue"
          />
          <i className="ri-shape-line text-base" />
          Показать оверлей виньетки
          <span className="text-text-muted text-xs ml-1">(Shift+drag: диаметр)</span>
        </label>
      )}

      {/* Face oval overlay toggle + Pin — shown only on common tab */}
      {effectiveTab === "common" && (
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer select-none">
            <input
              type="checkbox"
              checked={faceOvalOverlayEnabled}
              onChange={(e) => onFaceOvalOverlayToggle(e.target.checked)}
              className="accent-accent-orange"
            />
            <i className="ri-user-line text-base" />
            Показать овал зоны лица
            <span className="text-text-muted text-xs ml-1">(drag: перемещение)</span>
          </label>
          <button
            onClick={onFaceOvalPinToggle}
            className={`text-sm px-2 py-1 rounded transition-colors
              ${
                faceOvalPinned
                  ? "text-accent-orange bg-accent-orange/10"
                  : "text-text-muted hover:text-text-secondary"
              }`}
            title={
              faceOvalPinned
                ? "Открепить овал (автообновление)"
                : "Закрепить овал (без автообновления)"
            }
          >
            <i className={faceOvalPinned ? "ri-pushpin-2-fill" : "ri-pushpin-2-line"} />
          </button>
        </div>
      )}

      {/* Sliders */}
      <div className="space-y-3 max-h-[min(60vh,40rem)] overflow-y-auto pr-1">
        {visibleTabs
          .filter((g) => g.key === effectiveTab)
          .map((g) =>
            g.params
              .filter((paramKey) => shouldShowParam(paramKey as string))
              .map((paramKey) => {
                const def = getParamDef(g.key, paramKey as string);
                if (!def) return null;
                const path =
                  g.key === "common"
                    ? ["processing", paramKey as string]
                    : g.key === "vignette"
                      ? ["vignette", paramKey as string]
                      : ["processing", g.key, paramKey as string];
                if (isParamToggle(def)) {
                  return renderToggle(path, def, getValue(path));
                }
                return renderSlider(path, def, getValue(path));
              }),
          )}
      </div>
    </div>
  );
}
