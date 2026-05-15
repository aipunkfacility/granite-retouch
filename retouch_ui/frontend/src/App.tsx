import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { ImageUpload } from "./components/image-upload";
import { BeforeAfter } from "./components/before-after";
import { StepSelector } from "./components/step-selector";
import { ParamsPanel } from "./components/params-panel";
import { MachineSelector } from "./components/machine-selector";
import { ModuleSwitch } from "./components/module-switch";
import { MaterialSelector } from "./components/material-selector";
import { DiagnosticsPanel } from "./components/diagnostics-panel";
import { ConfigActions } from "./components/config-actions";
import { ExportButtons } from "./components/export-buttons";
import { usePreview } from "./hooks/use-preview";
import { useConfig } from "./hooks/use-config";
import { usePresetMaterial } from "./hooks/use-preset-material";
import type { MachineType, MaterialType, ConfigTree } from "./lib/types";
import { isConfigTree } from "./lib/types";
import type { VignetteParams } from "./lib/vignette-geometry";
import type { FaceOvalParams } from "./lib/face-oval-geometry";
import { deepMerge } from "./lib/utils";
import type { MachineType as MT } from "./lib/types";

/** Extract vignette params from config, with defaults */
function getVignetteParams(config: ConfigTree): VignetteParams {
  const v = (config.vignette ?? {}) as Record<string, unknown>;
  return {
    vertical_offset: (v.vertical_offset as number) ?? 0.1,
    vertical_diameter: (v.vertical_diameter as number) ?? 0.5,
    blur_radius: (v.blur_radius as number) ?? 60,
    headroom: (v.headroom as number) ?? 0.6,
    horizontal_oversize: (v.horizontal_oversize as number) ?? 0.2,
  };
}

/** Default face oval params */
const DEFAULT_FACE_OVAL: FaceOvalParams = {
  cx: 0.5,
  cy: 0.25,
  rx: 0.15,
  ry: 0.20,
  source: "heuristic",
};

/** Safely extract export_mode from config tree */
function getExportMode(config: ConfigTree | null, machineType: MT): string | undefined {
  if (!config?.processing) return undefined;
  const proc = config.processing as Record<string, unknown>;
  const machine = proc[machineType] as Record<string, unknown> | undefined;
  if (!machine) return undefined;
  return typeof machine.export_mode === "string" ? machine.export_mode : undefined;
}

export default function App() {
  // Toast state
  const [toast, setToast] = useState<string | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // State
  const [fileId, setFileId] = useState<string | null>(null);
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState("final");
  const [backendDown, setBackendDown] = useState(false);
  const [vignetteOverlayEnabled, setVignetteOverlayEnabled] = useState(false);
  const [faceOvalOverlayEnabled, setFaceOvalOverlayEnabled] = useState(false);
  const [faceOval, setFaceOval] = useState<FaceOvalParams | null>(null);
  const [faceOvalPinned, setFaceOvalPinned] = useState(false);

  // Dither preview state
  const [ditherImageUrl, setDitherImageUrl] = useState<string | null>(null);
  const [ditherLoading, setDitherLoading] = useState(false);
  const ditherAbortRef = useRef<AbortController | null>(null);

  // Hooks
  const { result: previewResult, loading, error: previewError, requestPreview } = usePreview(300);
  const { config, updateConfig, resetConfig, warnings: configWarnings } = useConfig();
  const pm = usePresetMaterial();

  // AUDIT-3.1: Синхронизировать faceOval из diagnostics preview → state
  useEffect(() => {
    if (previewResult?.diagnostics?.face_oval && !faceOvalOverlayEnabled && !faceOvalPinned) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing from external server diagnostics
      setFaceOval(previewResult.diagnostics.face_oval);
    }
  }, [previewResult, faceOvalOverlayEnabled, faceOvalPinned]);

  // Vignette params derived from config
  const vignetteParams = useMemo(() => getVignetteParams(config), [config]);

  // Image dimensions from preview diagnostics
  const imageWidth = previewResult?.diagnostics.width ?? 0;
  const imageHeight = previewResult?.diagnostics.height ?? 0;

  // Backend health check on mount
  useEffect(() => {
    let cancelled = false;
    const checkHealth = async () => {
      try {
        const res = await fetch("/api/health");
        if (!cancelled) setBackendDown(!res.ok);
      } catch {
        if (!cancelled) setBackendDown(true);
      }
    };
    checkHealth();
    return () => { cancelled = true; };
  }, []);

  // Cleanup Object URL when originalUrl changes or on unmount
  useEffect(() => {
    return () => {
      if (originalUrl) URL.revokeObjectURL(originalUrl);
    };
  }, [originalUrl]);

  // Helpers
  const requestPreviewWithOval = useCallback(
    (fid: string, mt: MachineType, cfg: ConfigTree) => {
      const oval = faceOvalOverlayEnabled ? faceOval : null;
      requestPreview(fid, mt, cfg, oval);
    },
    [faceOvalOverlayEnabled, faceOval, requestPreview],
  );

  // Handlers
  const handleImageUploaded = useCallback(
    (newFileId: string, previewUrl: string) => {
      setFileId(newFileId);
      setOriginalUrl(previewUrl);
      setFaceOval({ ...DEFAULT_FACE_OVAL });
      setFaceOvalPinned(false);
      setDitherImageUrl(null);
      requestPreview(newFileId, pm.machineType, config, faceOvalOverlayEnabled ? faceOval : null);
    },
    [pm.machineType, config, requestPreview, faceOvalOverlayEnabled, faceOval],
  );

  // Обработка выбора пресета из MachineSelector
  const handlePresetSelect = useCallback(
    (presetKey: string, presetConfig: ConfigTree, machineType: MachineType) => {
      pm.selectPreset(presetKey, presetConfig);
      // Обновить конфиг из пресета
      const merged = deepMerge(config as Record<string, unknown>, presetConfig as Record<string, unknown>);
      if (!isConfigTree(merged)) return;
      updateConfig(merged);
      if (fileId) requestPreviewWithOval(fileId, machineType, merged);
    },
    [config, pm, updateConfig, fileId, requestPreviewWithOval],
  );

  // Обработка выбора материала
  const handleMaterialSelect = useCallback(
    async (mat: MaterialType, currentConfig?: ConfigTree): Promise<{ success: boolean; validationWarnings: string[] }> => {
      const result = await pm.selectMaterial(mat, currentConfig);
      if (result.success) {
        // Применить config_patch к текущему конфигу
        // Это будет сделано через materialChanges + автоматическое обновление
        if (fileId) requestPreviewWithOval(fileId, pm.machineType, config as ConfigTree);
      }
      return result;
    },
    [pm, config, fileId, requestPreviewWithOval],
  );

  const handleConfigChangeByPath = useCallback(
    (path: string[], value: number | string) => {
      const newConfig = structuredClone(config);
      let obj: ConfigTree = newConfig;
      for (let i = 0; i < path.length - 1; i++) {
        const child = obj[path[i]];
        if (!isConfigTree(child)) {
          obj[path[i]] = {};
        }
        obj = obj[path[i]] as ConfigTree;
      }
      obj[path[path.length - 1]] = value;
      updateConfig(newConfig as ConfigTree);
      // Отметить параметр как overridden
      pm.markOverridden(path.join("."));
      if (fileId) requestPreviewWithOval(fileId, pm.machineType, newConfig);
    },
    [config, fileId, pm, updateConfig, requestPreviewWithOval],
  );

  const handleConfigChangeFull = useCallback(
    (newConfig: ConfigTree) => {
      updateConfig(newConfig);
      if (fileId) requestPreviewWithOval(fileId, pm.machineType, newConfig);
    },
    [fileId, pm.machineType, updateConfig, requestPreviewWithOval],
  );

  const handleReset = useCallback(
    (defaults: ConfigTree) => {
      resetConfig(defaults);
      if (fileId) requestPreviewWithOval(fileId, pm.machineType, defaults);
    },
    [fileId, pm.machineType, resetConfig, requestPreviewWithOval],
  );

  const handleFaceOvalChange = useCallback(
    (newOval: FaceOvalParams) => {
      setFaceOval(newOval);
      if (newOval.source === "manual" && !faceOvalPinned) {
        setFaceOvalPinned(true);
      }
      if (fileId) requestPreview(fileId, pm.machineType, config, newOval);
    },
    [fileId, pm.machineType, config, requestPreview, faceOvalPinned],
  );

  const handleFaceOvalPinToggle = useCallback(() => {
    setFaceOvalPinned((prev) => !prev);
  }, []);

  // Dither preview handler
  const handleRequestDitherPreview = useCallback(async () => {
    if (!fileId) return;

    if (previewResult?.diagnostics && !previewResult.diagnostics.numba_available) {
      const ok = window.confirm(
        "Без Numba дизеринг занимает 30-120 сек. Продолжить?"
      );
      if (!ok) return;
    }

    setDitherLoading(true);
    setDitherImageUrl(null);

    ditherAbortRef.current?.abort();
    const ac = new AbortController();
    ditherAbortRef.current = ac;

    try {
      const body: Record<string, unknown> = {
        file_id: fileId,
        machine: pm.machineType,
      };
      if (config) {
        body.params = { ...config, face_oval: faceOvalOverlayEnabled ? faceOval : null };
      }

      const res = await fetch("/api/process/dither-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ac.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setDitherImageUrl(data.image);
      setSelectedStep("dithered");
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      console.error("Dither preview error:", err);
      setToast(`Ошибка дизеринга: ${err instanceof Error ? err.message : err}`);
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      toastTimerRef.current = setTimeout(() => setToast(null), 3000);
    } finally {
      setDitherLoading(false);
    }
  }, [fileId, config, faceOvalOverlayEnabled, faceOval, previewResult, pm.machineType]);

  // Cleanup toast timer on unmount
  useEffect(() => {
    return () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); };
  }, []);

  // Compute available steps
  const availableSteps = useMemo(
    () =>
      previewResult
        ? { ...previewResult.images, ...(ditherImageUrl ? { dithered: ditherImageUrl } : {}) }
        : {},
    [previewResult, ditherImageUrl],
  );

  // Комби-пресеты для текущего combo_group
  const comboPresets = useMemo(() => {
    if (!pm.selectedPreset) return [];
    const entry = pm.catalog[pm.selectedPreset];
    if (!entry?.combo_group) return [];
    const cg = entry.combo_group;
    return Object.entries(pm.catalog)
      .filter(([, e]) => e.combo_group === cg)
      .map(([key, entry]) => ({ key, entry }));
  }, [pm.selectedPreset, pm.catalog]);

  const selectedEntry = pm.selectedPreset ? pm.catalog[pm.selectedPreset] : null;
  const brand = selectedEntry?.brand;

  // Layout
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex flex-col">
      {/* Backend down banner */}
      {backendDown && (
        <div className="bg-yellow-500/90 text-yellow-950 px-6 py-2 text-sm font-medium text-center border-b border-yellow-600">
          <i className="ri-error-warning-line mr-1" />
          Backend не запущен. Запустите: <code className="bg-yellow-600/20 px-1 rounded">make ui-backend</code>
        </div>
      )}

      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border shrink-0">
        <h1 className="text-xl font-heading font-semibold tracking-tight">
          <i className="ri-brush-line mr-2 text-accent-blue" />
          Granite Retouch
        </h1>
        <div className="flex gap-4 items-center">
          <MachineSelector
            groups={pm.catalogLoading ? [] : pm.groups}
            selectedPreset={pm.selectedPreset}
            machineType={pm.machineType}
            presetsCache={pm.presetsCache}
            onSelect={handlePresetSelect}
          />
          <ExportButtons fileId={fileId} machineType={pm.machineType} config={config} faceOval={faceOval} />
        </div>
      </header>

      {/* ModuleSwitch (только для комби-станков) */}
      {comboPresets.length > 1 && (
        <div className="px-6 py-2 border-b border-border bg-bg-card/50">
          <span className="text-xs text-text-muted mr-2">
            {brand === "sauno" ? "САУНО" : brand === "stanzone" ? "Stanzone" : brand === "mirtels" ? "Mirtels" : ""} — модуль:
          </span>
          <ModuleSwitch
            comboPresets={comboPresets}
            selectedPreset={pm.selectedPreset}
            presetsCache={pm.presetsCache}
            onSelect={handlePresetSelect}
          />
        </div>
      )}

      {/* Config warnings banner */}
      {configWarnings.length > 0 && (
        <div className="bg-accent-orange/10 text-accent-orange px-6 py-2 text-sm border-b border-accent-orange/20">
          {configWarnings.map((w, i) => (
            <span key={`warning-${i}`}>
              {i > 0 ? " · " : ""}{w}
            </span>
          ))}
        </div>
      )}

      {/* Numba not available banner */}
      {previewResult?.diagnostics && !previewResult.diagnostics.numba_available && (
        <div className="bg-yellow-500/10 text-yellow-700 px-6 py-2 text-sm border-b border-yellow-500/20 flex items-center gap-2">
          <i className="ri-speed-line" />
          Дизеринг без Numba — медленно (30–120 сек). Установите: <code className="bg-yellow-500/20 px-1 rounded">uv sync --extra fast</code>
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar: parameters */}
        <aside className="w-80 border-r border-border overflow-y-auto p-4 space-y-4 shrink-0">
          {!fileId ? (
            <ImageUpload onImageUploaded={handleImageUploaded} />
          ) : (
            <>
              {/* Material selector */}
              <MaterialSelector
                material={pm.material}
                machineType={pm.machineType}
                profiles={pm.profiles}
                materialChanges={pm.materialChanges}
                validationWarnings={pm.validationWarnings}
                activeHint={pm.activeHint}
                onSelect={handleMaterialSelect}
                currentConfig={config}
              />

              <ParamsPanel
                machineType={pm.machineType}
                config={config}
                onConfigChange={handleConfigChangeByPath}
                vignetteOverlayEnabled={vignetteOverlayEnabled}
                onVignetteOverlayToggle={setVignetteOverlayEnabled}
                faceOvalOverlayEnabled={faceOvalOverlayEnabled}
                onFaceOvalOverlayToggle={setFaceOvalOverlayEnabled}
                faceOvalPinned={faceOvalPinned}
                onFaceOvalPinToggle={handleFaceOvalPinToggle}
                overriddenKeys={pm.overriddenKeys}
                onResetParam={(key: string) => {
                  const baseline = pm.resetParam(key);
                  if (baseline) {
                    // Сбросить параметр к значению пресета
                    const newConfig = structuredClone(config);
                    const parts = key.split(".");
                    let obj: Record<string, unknown> = newConfig as Record<string, unknown>;
                    let baselineObj: Record<string, unknown> = baseline as Record<string, unknown>;
                    for (let i = 0; i < parts.length - 1; i++) {
                      if (!isConfigTree(obj[parts[i]])) obj[parts[i]] = {};
                      obj = obj[parts[i]] as Record<string, unknown>;
                      if (!isConfigTree(baselineObj[parts[i]])) baselineObj[parts[i]] = {};
                      baselineObj = baselineObj[parts[i]] as Record<string, unknown>;
                    }
                    if (baselineObj[parts[parts.length - 1]] !== undefined) {
                      obj[parts[parts.length - 1]] = baselineObj[parts[parts.length - 1]];
                      updateConfig(newConfig as ConfigTree);
                    }
                  }
                }}
              />
              <div className="border-t border-border pt-4">
                <ConfigActions
                  config={config}
                  presetsCache={pm.presetsCache}
                  onConfigReset={handleReset}
                  onConfigChange={handleConfigChangeFull}
                />
              </div>
              <div className="border-t border-border pt-4">
                <DiagnosticsPanel
                  diagnostics={previewResult?.diagnostics ?? null}
                  warnings={previewResult?.warnings ?? []}
                />
              </div>
              {/* Change image button */}
              <button
                onClick={() => {
                  setFileId(null);
                  setOriginalUrl(null);
                  setFaceOval(null);
                  setFaceOvalPinned(false);
                  setDitherImageUrl(null);
                }}
                className="text-sm text-text-muted hover:text-text-secondary transition-colors flex items-center gap-1"
              >
                <i className="ri-image-add-line" />
                Сменить изображение
              </button>
            </>
          )}
        </aside>

        {/* Main area: image preview */}
        <main className="flex-1 p-4 flex flex-col gap-3 overflow-y-auto">
          {previewResult ? (
            <>
              <StepSelector
                selectedStep={selectedStep}
                onStepChange={setSelectedStep}
                availableSteps={Object.keys(availableSteps)}
                exportMode={getExportMode(config, pm.machineType)}
                onRequestDitherPreview={handleRequestDitherPreview}
                ditherLoading={ditherLoading}
              />
              <BeforeAfter
                originalUrl={originalUrl}
                images={availableSteps}
                selectedStep={selectedStep}
                onStepChange={setSelectedStep}
                vignetteOverlayEnabled={vignetteOverlayEnabled}
                faceOvalOverlayEnabled={faceOvalOverlayEnabled}
                faceOval={faceOval}
                onFaceOvalChange={handleFaceOvalChange}
                imageWidth={imageWidth}
                imageHeight={imageHeight}
                vignetteParams={vignetteParams}
                onVignetteParamChange={handleConfigChangeByPath}
              />
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-text-muted">
              {loading ? (
                <div className="flex items-center gap-2">
                  <i className="ri-loader-4-line animate-spin text-xl" />
                  <span>Обработка...</span>
                </div>
              ) : (
                <div className="text-center">
                  <i className="ri-image-line text-4xl block mb-2 text-text-muted/50" />
                  <span>Загрузите изображение для предпросмотра</span>
                </div>
              )}
            </div>
          )}
          {previewError && (
            <p className="text-accent-red text-sm">
              <i className="ri-error-warning-line mr-1" />
              {previewError}
            </p>
          )}
        </main>
      </div>

      {/* Toast notification */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-bg-card border border-border text-text-primary px-5 py-3 rounded-lg shadow-lg z-50 text-sm max-w-md">
          {toast}
        </div>
      )}
    </div>
  );
}
