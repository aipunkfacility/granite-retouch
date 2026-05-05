/** Processing diagnostics: face brightness, glow, black ratio */

interface DiagnosticsData {
  glow_size: number;
  glow_opacity: number;
  face_brightness_before: number;
  face_brightness_after: number;
  face_correction_factor: number;
  black_ratio: number;
  blue_ratio: number;
  width: number;
  height: number;
}

interface Props {
  diagnostics: DiagnosticsData | null;
  warnings: string[];
}

export function DiagnosticsPanel({ diagnostics, warnings }: Props) {
  if (!diagnostics) return null;

  return (
    <div className="bg-bg-card rounded-lg p-4 space-y-2">
      <h3 className="font-heading font-semibold text-text-primary text-sm">Диагностика</h3>

      <div className="space-y-1 text-sm">
        <p className="text-text-secondary">
          <span className="text-text-muted">Face:</span>{" "}
          {diagnostics.face_brightness_before.toFixed(1)} → {diagnostics.face_brightness_after.toFixed(1)}
          <span className="text-text-muted ml-2">
            (factor: {diagnostics.face_correction_factor.toFixed(3)})
          </span>
        </p>

        <p className="text-text-secondary">
          <span className="text-text-muted">Glow:</span>{" "}
          {diagnostics.glow_size}px / {(diagnostics.glow_opacity * 100).toFixed(0)}%
        </p>

        <p className="text-text-secondary">
          <span className="text-text-muted">Black:</span>{" "}
          {(diagnostics.black_ratio * 100).toFixed(1)}%
          <span className="text-text-muted ml-2">Blue:</span>{" "}
          {(diagnostics.blue_ratio * 100).toFixed(1)}%
        </p>

        <p className="text-text-muted text-xs">
          {diagnostics.width}×{diagnostics.height}
        </p>
      </div>

      {warnings.length > 0 && (
        <div className="mt-2 space-y-1">
          {warnings.map((w, i) => (
            <p key={i} className="text-sm text-accent-orange">
              <i className="ri-alert-line mr-1" />
              {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
