/** TIFF/PNG export by fileId */
import { useState } from "react";
import { fetchExport } from "../lib/api";

interface Props {
  fileId: string | null;
  machineType: "laser" | "impact";
  config: Record<string, any>;
}

export function ExportButtons({ fileId, machineType, config }: Props) {
  const [exporting, setExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<"tiff" | "png" | null>(null);

  const handleExport = async (format: "tiff" | "png") => {
    if (!fileId) return;
    setExporting(true);
    setExportFormat(format);
    try {
      const blob = await fetchExport(fileId, machineType, format, config);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `retouch_result.${format === "tiff" ? "tif" : "png"}`;
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

  return (
    <div className="flex gap-2">
      <button
        onClick={() => handleExport("tiff")}
        disabled={!fileId || exporting}
        className="px-4 py-1.5 bg-bg-card text-text-primary text-sm rounded hover:bg-bg-hover disabled:opacity-50 transition-colors flex items-center gap-1"
      >
        {exporting && exportFormat === "tiff" ? (
          <i className="ri-loader-4-line animate-spin" />
        ) : (
          <i className="ri-image-line" />
        )}
        TIFF
      </button>
      <button
        onClick={() => handleExport("png")}
        disabled={!fileId || exporting}
        className="px-4 py-1.5 bg-bg-card text-text-primary text-sm rounded hover:bg-bg-hover disabled:opacity-50 transition-colors flex items-center gap-1"
      >
        {exporting && exportFormat === "png" ? (
          <i className="ri-loader-4-line animate-spin" />
        ) : (
          <i className="ri-image-line" />
        )}
        PNG
      </button>
    </div>
  );
}
