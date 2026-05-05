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
  source: string;
  warnings: string[];
}

export interface PresetItem {
  name: string;
  config: Record<string, any>;
}

/** Upload image — returns file_id */
export async function uploadImage(file: File): Promise<{ file_id: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/process/upload`, {
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
  machineType: "laser" | "impact",
  configOverride?: Record<string, any>,
  signal?: AbortSignal,
): Promise<PreviewResult> {
  const formData = new FormData();
  formData.append("file_id", fileId);
  formData.append("machine_type", machineType);
  if (configOverride) {
    formData.append("config_json", JSON.stringify(configOverride));
  }

  const res = await fetch(`${API_BASE}/process/preview`, {
    method: "POST",
    body: formData,
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
  machineType: "laser" | "impact",
  format: "tiff" | "png",
  configOverride?: Record<string, any>,
): Promise<Blob> {
  const formData = new FormData();
  formData.append("file_id", fileId);
  formData.append("machine_type", machineType);
  formData.append("format", format);
  if (configOverride) {
    formData.append("config_json", JSON.stringify(configOverride));
  }

  const res = await fetch(`${API_BASE}/process/export`, {
    method: "POST",
    body: formData,
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
export async function fetchDefaults(): Promise<ConfigResult> {
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
