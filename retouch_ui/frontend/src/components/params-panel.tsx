import { useState } from "react";
import { PARAM_SECTIONS } from "../lib/config-schema";
import type { MachineType, ConfigTree } from "../lib/types";
import { ParamGroup } from "./param-group";

interface Props {
  machineType: MachineType;
  config: ConfigTree;
  onConfigChange: (path: string[], value: number | string) => void;
  overriddenKeys?: Set<string>;
  onResetParam?: (key: string) => void;
}

export function ParamsPanel({
  machineType,
  config,
  onConfigChange,
  overriddenKeys,
  onResetParam,
}: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const visibleSections = PARAM_SECTIONS.filter((section) => {
    if (section.key === "advanced" && !showAdvanced) return false;
    if ("machineType" in section && section.machineType !== machineType) return false;
    return true;
  });

  return (
    <div className="space-y-3">
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

      <div className="space-y-1">
        {visibleSections.map((section) => (
          <ParamGroup
            key={section.key}
            section={section}
            config={config}
            machineType={machineType}
            overriddenKeys={overriddenKeys}
            defaultCollapsed={true}
            onConfigChange={onConfigChange}
            onResetParam={onResetParam}
          />
        ))}
      </div>


    </div>
  );
}
