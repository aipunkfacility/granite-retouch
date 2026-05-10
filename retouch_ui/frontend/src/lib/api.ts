import type { MachineType, ConfigTree } from "./types";
import type { FaceOvalParams } from "./face-oval-geometry";

const API_BASE = "/api";

export interface PreviewResult {
  images: Record<string, string>;
  diagnostics: {
    glow_size: number;
    glow_opacity: number;
    face_brightness_before: number;
    face_brightness_after: number;
    face_correction_factor: number;
    black_ratio: number;
    blue_ratio: number;
    width: number;
    height: number;
    // AUDIT-3.1: face_oval из preview для передачи в export
    face_oval?: FaceOvalParams | null;
  };
  warnings: string[];
}

/** Параметры предпросмотра — соответствует backend PreviewParams.

 * UI передаёт полный конфиг как configOverride — вложенные секции
 * (processing.laser_80w.*, vignette.* и т.д.) проходят через
 * PreviewParams с extra="allow" на backend.
 */
export interface PreviewParams {
  face_oval?: FaceOvalParams | null;
  stone_type?: string | null;
  step_mm?: number | null;
  [key: string]: unknown;  // позволяет передавать вложенные секции конфига
}

export interface ConfigResult {
  config: ConfigTree;
  warnings: string[];
}

export interface DefaultsResult {
  defaults: ConfigTree;
}

export interface VignetteMaskResult {
  mask: string;
  params: {
    arch_top_y: number;
    arch_bottom_y: number;
    h_oversize: number;
  };
}

export interface PresetItem {
  name: string;
  config: ConfigTree;
}

/** Upload image — returns file_id. 120s timeout. */
export async function uploadImage(file: File): Promise<{ file_id: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120_000);

  try {
    const res = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Upload failed: ${err}`);
    }

    return res.json();
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("Загрузка превышена (120 сек). Проверьте подключение к backend.");
    }
    if (e instanceof TypeError) {
      // TypeError = сетевая ошибка (backend недоступен)
      throw new Error("Backend недоступен. Убедитесь что сервер запущен (make ui-backend).");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

/** Preview processing — by file_id */
export async function fetchPreview(
  fileId: string,
  machineType: MachineType,
  configOverride?: ConfigTree,
  signal?: AbortSignal,
  faceOval?: FaceOvalParams | null,
  fullSteps: boolean = true,
): Promise<PreviewResult> {
  const body: Record<string, unknown> = {
    file_id: fileId,
    machine: machineType,
    full_steps: fullSteps,
  };
  if (configOverride || faceOval) {
    const params: Record<string, unknown> = configOverride ? { ...configOverride } : {};
    if (faceOval) {
      params.face_oval = faceOval;
    }
    body.params = params;
  }

  const res = await fetch(`${API_BASE}/process/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Preview failed: ${err}`);
  }

  return res.json();
}

/** Export result — by file_id */
export async function fetchExport(
  fileId: string,
  machineType: MachineType,
  format: "bmp" | "bmp_1bit" | "bmp_8bit" | "png" | "tiff",
  configOverride?: ConfigTree,
  faceOval?: FaceOvalParams | null,
): Promise<Blob> {
  const body: Record<string, unknown> = {
    file_id: fileId,
    machine: machineType,
    format,
  };
  if (configOverride || faceOval) {
    const params: Record<string, unknown> = configOverride ? { ...configOverride } : {};
    if (faceOval) {
      params.face_oval = faceOval;
    }
    body.params = params;
  }

  const res = await fetch(`${API_BASE}/process/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Export failed: ${err}`);
  }

  return res.blob();
}

/** Get config */
export async function fetchConfig(): Promise<ConfigResult> {
  const res = await fetch(`${API_BASE}/config`);
  return res.json();
}

/** Save config */
export async function saveConfig(config: ConfigTree): Promise<{ saved: boolean; warnings: string[] }> {
  const res = await fetch(`${API_BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
  return res.json();
}

/** Default config */
export async function fetchDefaults(): Promise<DefaultsResult> {
  const res = await fetch(`${API_BASE}/config/defaults`);
  return res.json();
}

/** List presets */
export async function fetchPresets(): Promise<{ presets: PresetItem[] }> {
  const res = await fetch(`${API_BASE}/presets`);
  return res.json();
}

/** Create preset */
export async function createPreset(name: string, config: ConfigTree) {
  const res = await fetch(`${API_BASE}/presets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, config }),
  });
  return res.json();
}

/** Delete preset */
export async function deletePreset(name: string) {
  const res = await fetch(`${API_BASE}/presets/${name}`, { method: "DELETE" });
  return res.json();
}

/** Vignette mask — generates arch mask by params (no image needed) */
export async function fetchVignetteMask(
  width: number,
  height: number,
  vignetteParams: Record<string, number>,
  signal?: AbortSignal,
): Promise<VignetteMaskResult> {
  const res = await fetch(`${API_BASE}/vignette/mask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ width, height, vignette: vignetteParams }),
    signal,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Vignette mask failed: ${err}`);
  }
  return res.json();
}
