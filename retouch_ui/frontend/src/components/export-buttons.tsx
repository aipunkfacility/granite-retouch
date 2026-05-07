/** BMP/PNG export by fileId — CNC stone engraving output formats */
import { useState } from "react";
import { fetchExport } from "../lib/api";
import type { MachineType } from "../lib/types";

type ExportFormat = "bmp" | "bmp_1bit" | "bmp_8bit" | "png" | "tiff";

interface Props {
  fileId: string | null;
  machineType: MachineType;
  config: Record<string, any>;
}

/** Default export format per machine type */
function defaultFormat(machineType: MachineType): ExportFormat {
  switch (machineType) {
    case "laser_80w": return "bmp_1bit";
    case "impact": return "bmp_8bit";
    default: return "bmp";
  }
}

/** File extension for download */
function formatExt(format: ExportFormat): string {
  if (format === "tiff") return "tif";
  if (format === "png") return "png";
  return "bmp";
}

/** Human-readable label */
function formatLabel(format: ExportFormat): string {
  switch (format) {
    case "bmp": return "BMP";
    case "bmp_8bit": return "BMP 8-bit";
    case "bmp_1bit": return "BMP 1-bit";
    case "png": return "PNG";
    case "tiff": return "TIFF";
  }
}

export function ExportButtons({ fileId, machineType, config }: Props) {
  const [exporting, setExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<ExportFormat | null>(null);

  const handleExport = async (format: ExportFormat) => {
    if (!fileId) return;
    setExporting(true);
    setExportFormat(format);
    try {
      const blob = await fetchExport(fileId, machineType, format, config);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `retouch_result.${formatExt(format)}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      alert(`Ошибка экспорта: ${msg}`);
    } finally {
      setExporting(false);
      setExportFormat(null);
    }
  };

  const primaryFormat = defaultFormat(machineType);

  return (
    <div className="flex gap-2 items-center">
      {/* Primary export button (format depends on machine type) */}
      <button
        onClick={() => handleExport(primaryFormat)}
        disabled={!fileId || exporting}
        className="px-4 py-1.5 bg-accent-blue text-white text-sm rounded hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-1"
        title={`Экспорт ${formatLabel(primaryFormat)} (по умолчанию для ${machineType})`}
      >
        {exporting && exportFormat === primaryFormat ? (
          <i className="ri-loader-4-line animate-spin" />
        ) : (
          <i className="ri-download-line" />
        )}
        {formatLabel(primaryFormat)}
      </button>

      {/* PNG preview */}
      <button
        onClick={() => handleExport("png")}
        disabled={!fileId || exporting}
        className="px-4 py-1.5 bg-bg-card text-text-primary text-sm rounded hover:bg-bg-hover disabled:opacity-50 transition-colors flex items-center gap-1"
        title="PNG для предпросмотра"
      >
        {exporting && exportFormat === "png" ? (
          <i className="ri-loader-4-line animate-spin" />
        ) : (
          <i className="ri-image-line" />
        )}
        PNG
      </button>

      {/* More formats dropdown */}
      <div className="relative group">
        <button
          disabled={!fileId || exporting}
          className="px-2 py-1.5 bg-bg-card text-text-primary text-sm rounded hover:bg-bg-hover disabled:opacity-50 transition-colors"
          title="Другие форматы"
        >
          <i className="ri-arrow-down-s-line" />
        </button>
        <div className="absolute right-0 top-full mt-1 bg-bg-card border border-border rounded shadow-lg z-50 hidden group-hover:block min-w-[140px]">
          {(["bmp", "bmp_8bit", "bmp_1bit", "tiff"] as ExportFormat[]).map((fmt) => (
            <button
              key={fmt}
              onClick={() => handleExport(fmt)}
              className="w-full text-left px-3 py-2 text-sm text-text-primary hover:bg-bg-hover transition-colors"
            >
              {formatLabel(fmt)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
