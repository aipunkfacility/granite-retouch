/** Processing diagnostics: face brightness, glow, black ratio */

import type { DiagnosticsData } from "../lib/api";

interface Props {
  diagnostics: DiagnosticsData | null;
  warnings: string[];
}

export function DiagnosticsPanel({ diagnostics, warnings }: Props) {
  if (!diagnostics) return null;

  const brightnessDelta = diagnostics.face_brightness_after - diagnostics.face_brightness_before;
  const brightnessColor = brightnessDelta >= 0 ? "text-accent-green" : "text-accent-red";
  const brightnessSign = brightnessDelta >= 0 ? "+" : "";

  const blackRatio = diagnostics.black_ratio;
  const blackColor = blackRatio < 0.3 ? "text-accent-green" : blackRatio <= 0.5 ? "text-accent-orange" : "text-accent-red";

  return (
    <div className="bg-bg-card rounded-lg p-4 space-y-2">
      <h3 className="font-heading font-semibold text-text-primary text-sm">Диагностика</h3>

      <div className="space-y-1 text-sm">
        <p className="text-text-secondary" title="Яркость зоны лица до и после коррекции. Целевой диапазон: 180-230.">
          <span className="text-text-muted">Face:</span>{" "}
          {diagnostics.face_brightness_before.toFixed(1)} → {diagnostics.face_brightness_after.toFixed(1)}
          <span className={`ml-2 ${brightnessColor}`}>
            ({brightnessSign}{brightnessDelta.toFixed(1)})
          </span>
          <span className="text-text-muted ml-2">
            factor: {diagnostics.face_correction_factor.toFixed(3)}
          </span>
        </p>

        <p className="text-text-secondary" title="Размер и непрозрачность свечения вокруг контура.">
          <span className="text-text-muted">Glow:</span>{" "}
          {diagnostics.glow_size}px / {(diagnostics.glow_opacity * 100).toFixed(0)}%
        </p>

        <p className="text-text-secondary">
          <span className={`text-text-muted`} title="Доля чёрного в итоговом изображении. Норма: 20-40%.">Black:</span>{" "}
          <span className={blackColor}>{(blackRatio * 100).toFixed(1)}%</span>
          <span className="text-text-muted ml-2" title="Доля синего канала. Высокое значение может указывать на брак.">Blue:</span>{" "}
          {(diagnostics.blue_ratio * 100).toFixed(1)}%
        </p>

        <p className="text-text-muted text-xs">
          {diagnostics.width}×{diagnostics.height}
        </p>
      </div>

      {warnings.length > 0 && (
        <div className="mt-2 space-y-1">
          {warnings.map((w, i) => (
            <p key={`diagnostic-warning-${i}`} className="text-sm text-accent-orange">
              <i className="ri-alert-line mr-1" />
              {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
