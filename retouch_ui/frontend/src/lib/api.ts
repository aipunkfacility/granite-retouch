import type { MachineType } from "./types";

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
  };
  warnings: string[];
}

export interface ConfigResult {
  config: Record<string, any>;
  warnings: string[];
}

export interface DefaultsResult {
  defaults: Record<string, any>;
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
  config: Record<string, any>;
}

/** Upload image — returns file_id */
export async function uploadImage(file: File): Promise<{ file_id: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Upload failed: ${err}`);
  }

  return res.json();
}

/** Preview processing — by file_id */
export async function fetchPreview(
  fileId: string,
  machineType: MachineType,
  configOverride?: Record<string, any>,
  signal?: AbortSignal,
): Promise<PreviewResult> {
  const body: Record<string, any> = {
    file_id: fileId,
    machine: machineType,
  };
  if (configOverride) {
    body.params = configOverride;
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
  format: "tiff" | "png",
  configOverride?: Record<string, any>,
): Promise<Blob> {
  const body: Record<string, any> = {
    file_id: fileId,
    machine: machineType,
    format,
  };
  if (configOverride) {
    body.params = configOverride;
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
export async function saveConfig(config: Record<string, any>): Promise<{ saved: boolean; warnings: string[] }> {
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
export async function createPreset(name: string, config: Record<string, any>) {
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
