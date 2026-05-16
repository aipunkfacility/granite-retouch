/** BMP/PNG export by fileId — CNC stone engraving output formats */
import { useState, useRef, useCallback } from "react";
import { fetchExport } from "../lib/api";
import type { MachineType, ConfigTree } from "../lib/types";
import type { FaceOvalParams } from "../lib/face-oval-geometry";
import { useToast } from "./toast-provider";

type ExportFormat = "bmp" | "bmp_1bit" | "bmp_8bit" | "png" | "tiff";

const DROPDOWN_FORMATS: ExportFormat[] = ["bmp", "bmp_8bit", "bmp_1bit", "tiff"];

interface Props {
  fileId: string | null;
  machineType: MachineType;
  config: ConfigTree;
  faceOval?: FaceOvalParams | null;
  processing?: boolean;
}

/** Default export format per machine type */
function defaultFormat(machineType: MachineType): ExportFormat {
  switch (machineType) {
    case "laser_80w": return "bmp_8bit";
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

export function ExportButtons({ fileId, machineType, config, faceOval, processing }: Props) {
  const [exporting, setExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<ExportFormat | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [dropdownIndex, setDropdownIndex] = useState(0);
  const dropdownBtnRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const { showToast } = useToast();

  const handleExport = useCallback(async (format: ExportFormat) => {
    if (!fileId) return;
    setExporting(true);
    setExportFormat(format);
    setDropdownOpen(false);
    try {
      const blob = await fetchExport(fileId, machineType, format, config, faceOval);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `retouch_result.${formatExt(format)}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`Ошибка экспорта: ${msg}`, { type: 'error', duration: 3000 });
    } finally {
      setExporting(false);
      setExportFormat(null);
    }
  }, [fileId, machineType, config, faceOval, showToast]);

  const handleDropdownKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!dropdownOpen) {
        if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setDropdownOpen(true);
          setDropdownIndex(0);
        }
        return;
      }

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setDropdownIndex((prev) => {
            const next = Math.min(prev + 1, DROPDOWN_FORMATS.length - 1);
            dropdownBtnRefs.current[next]?.focus();
            return next;
          });
          break;
        case "ArrowUp":
          e.preventDefault();
          setDropdownIndex((prev) => {
            const next = Math.max(prev - 1, 0);
            dropdownBtnRefs.current[next]?.focus();
            return next;
          });
          break;
        case "Escape":
          e.preventDefault();
          setDropdownOpen(false);
          break;
        case "Enter":
          e.preventDefault();
          handleExport(DROPDOWN_FORMATS[dropdownIndex]);
          break;
      }
    },
    [dropdownOpen, dropdownIndex, handleExport],
  );

  const primaryFormat = defaultFormat(machineType);

  const disabledReason = !fileId ? "Загрузите изображение" : processing ? "Дождитесь обработки" : null;

  return (
    <div className="flex gap-2 items-center relative">
      {/* Primary export button (format depends on machine type) */}
      <button
        onClick={() => handleExport(primaryFormat)}
        disabled={!!disabledReason || exporting}
        className="px-3 py-1.5 bg-accent-blue text-white text-sm rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity duration-200 flex items-center gap-1"
        title={disabledReason ?? `Экспорт ${formatLabel(primaryFormat)} (по умолчанию для ${machineType})`}
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
        disabled={!!disabledReason || exporting}
        className="px-3 py-1.5 bg-bg-card text-text-primary text-sm rounded-lg hover:bg-bg-hover disabled:opacity-50 transition-colors duration-200 flex items-center gap-1"
        title={disabledReason ?? "PNG для предпросмотра"}
      >
        {exporting && exportFormat === "png" ? (
          <i className="ri-loader-4-line animate-spin" />
        ) : (
          <i className="ri-image-line" />
        )}
        PNG
      </button>

      {/* More formats dropdown */}
      <div className="relative">
        <button
          disabled={!!disabledReason || exporting}
          className="px-3 py-1.5 bg-bg-card text-text-primary text-sm rounded-lg hover:bg-bg-hover disabled:opacity-50 transition-colors duration-200"
          title={disabledReason ?? "Другие форматы"}
          onClick={() => {
            setDropdownOpen((prev) => !prev);
            setDropdownIndex(0);
          }}
          onKeyDown={handleDropdownKeyDown}
          onBlur={() => {
            // Close dropdown when focus leaves the dropdown area
            setTimeout(() => setDropdownOpen(false), 150);
          }}
        >
          <i className="ri-arrow-down-s-line" />
        </button>
        {dropdownOpen && (
          <div className="absolute right-0 top-full mt-1 bg-bg-card border border-border rounded-lg shadow-lg z-50 min-w-[140px]">
            {DROPDOWN_FORMATS.map((fmt, idx) => (
              <button
                key={fmt}
                ref={(el) => { dropdownBtnRefs.current[idx] = el; }}
                onClick={() => handleExport(fmt)}
                onKeyDown={handleDropdownKeyDown}
                className={`w-full text-left px-3 py-2 text-sm text-text-primary hover:bg-bg-hover transition-colors duration-200
                  ${idx === dropdownIndex ? "bg-bg-hover" : ""}`}
              >
                {formatLabel(fmt)}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
