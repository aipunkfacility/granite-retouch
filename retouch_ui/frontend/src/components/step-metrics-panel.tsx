import { useState } from "react";
import type { StepMetricsData, ZoneMetricsData } from "../lib/api";

interface Props {
  stepMetrics: StepMetricsData[] | undefined;
}

function ZoneMetricsRow({ zone, metrics }: { zone: string; metrics: ZoneMetricsData }) {
  const clippedColor = metrics.clipped_pct > 10 ? "text-accent-red" : metrics.clipped_pct > 3 ? "text-accent-orange" : "text-accent-green";
  return (
    <tr className="text-xs font-mono border-b border-border/50">
      <td className="px-2 py-1 text-text-secondary font-medium">{zone}</td>
      <td className="px-2 py-1 text-right">{metrics.median.toFixed(1)}</td>
      <td className="px-2 py-1 text-right text-text-muted">{metrics.p10.toFixed(1)}</td>
      <td className="px-2 py-1 text-right text-text-muted">{metrics.p90.toFixed(1)}</td>
      <td className="px-2 py-1 text-right text-text-muted">{metrics.p95.toFixed(1)}</td>
      <td className="px-2 py-1 text-right text-text-muted">{metrics.max.toFixed(0)}</td>
      <td className="px-2 py-1 text-right text-text-muted">{metrics.variance.toFixed(1)}</td>
      <td className={`px-2 py-1 text-right ${clippedColor}`}>{metrics.clipped_pct.toFixed(1)}%</td>
    </tr>
  );
}

function StepMetricsTable({ record }: { record: StepMetricsData }) {
  const zoneNames = Object.keys(record.zone_metrics);
  if (zoneNames.length === 0) return null;

  return (
    <div className="mb-2">
      <div className="text-xs font-heading font-semibold text-text-primary mb-1">
        {record.step_name}
        <span className="text-text-muted font-normal ml-2 font-mono">{record.timestamp_ms}ms</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-xxs text-text-muted uppercase border-b border-border">
              <th className="px-2 py-0.5 text-left font-medium">Zone</th>
              <th className="px-2 py-0.5 text-right font-medium">Median</th>
              <th className="px-2 py-0.5 text-right font-medium">P10</th>
              <th className="px-2 py-0.5 text-right font-medium">P90</th>
              <th className="px-2 py-0.5 text-right font-medium">P95</th>
              <th className="px-2 py-0.5 text-right font-medium">Max</th>
              <th className="px-2 py-0.5 text-right font-medium">Var</th>
              <th className="px-2 py-0.5 text-right font-medium">Clip</th>
            </tr>
          </thead>
          <tbody>
            {zoneNames.map((zone) => (
              <ZoneMetricsRow key={zone} zone={zone} metrics={record.zone_metrics[zone]} />
            ))}
          </tbody>
        </table>
      </div>
      {record.warnings.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {record.warnings.map((w, i) => (
            <p key={`sw-${i}`} className="text-xs text-accent-orange">
              <i className="ri-alert-line mr-1" />
              {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export function StepMetricsPanel({ stepMetrics }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  if (!stepMetrics || stepMetrics.length === 0) return null;

  return (
    <div className="bg-bg-card rounded-lg p-4 space-y-2">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center justify-between font-heading font-semibold text-text-primary text-sm"
      >
        <span>Step Metrics</span>
        <i className={`ri-${collapsed ? "arrow-down-s" : "arrow-up-s"}-line text-text-muted`} />
      </button>

      {!collapsed && (
        <div className="space-y-3">
          {stepMetrics.map((record, idx) => (
            <StepMetricsTable key={`${record.step_name}-${idx}`} record={record} />
          ))}

          {stepMetrics.length === 0 && (
            <p className="text-xs text-text-muted">No step metrics recorded</p>
          )}
        </div>
      )}
    </div>
  );
}
