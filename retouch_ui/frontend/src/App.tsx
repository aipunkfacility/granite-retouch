import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { ImageUpload } from "./components/image-upload";
import { BeforeImage } from "./components/before-image";
import { AfterImage } from "./components/after-image";
import { StepSelector, STEP_LABELS } from "./components/step-selector";
import { ParamsPanel } from "./components/params-panel";
import { MachineSelector } from "./components/machine-selector";
import { ModuleSwitch } from "./components/module-switch";
import { MaterialSelector } from "./components/material-selector";
import { DiagnosticsPanel } from "./components/diagnostics-panel";
import { ConfigActions } from "./components/config-actions";
import { ExportButtons } from "./components/export-buttons";
import { ProfileSelector } from "./components/profile-selector";
import { StepMetricsPanel } from "./components/step-metrics-panel";
import { useToast } from "./components/toast-provider";
import { usePreview } from "./hooks/use-preview";
import { useConfig } from "./hooks/use-config";
import { usePresetMaterial } from "./hooks/use-preset-material";
import type { MachineType, MaterialType, ConfigTree, ProfileType } from "./lib/types";
import { isConfigTree } from "./lib/types";
import type { VignetteParams } from "./lib/vignette-geometry";
import type { FaceOvalParams } from "./lib/face-oval-geometry";
import { deepMerge } from "./lib/utils";
import type { MachineType as MT } from "./lib/types";

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

const DEFAULT_FACE_OVAL: FaceOvalParams = {
  cx: 0.5,
  cy: 0.25,
  rx: 0.15,
  ry: 0.20,
  source: "heuristic",
};

function getExportMode(config: ConfigTree | null, machineType: MT): string | undefined {
  if (!config?.processing) return undefined;
  const proc = config.processing as Record<string, unknown>;
  const machine = proc[machineType] as Record<string, unknown> | undefined;
  if (!machine) return undefined;
  return typeof machine.export_mode === "string" ? machine.export_mode : undefined;
}

export default function App() {
  const { showToast } = useToast();

  const [fileId, setFileId] = useState<string | null>(null);
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState("final");
  const [backendDown, setBackendDown] = useState(false);
  const [faceOvalOverlayEnabled, setFaceOvalOverlayEnabled] = useState(false);
  const [faceOval, setFaceOval] = useState<FaceOvalParams | null>(null);
  const [faceOvalPinned, setFaceOvalPinned] = useState(false);
  const [paramsCollapsed, setParamsCollapsed] = useState(false);
  const [leftColHidden, setLeftColHidden] = useState(false);
  const [compareMode, setCompareMode] = useState(false);

  const [ditherImageUrl, setDitherImageUrl] = useState<string | null>(null);
  const [ditherLoading, setDitherLoading] = useState(false);
  const ditherAbortRef = useRef<AbortController | null>(null);

  const [profile, setProfile] = useState<ProfileType>("standard");

  const { result: previewResult, loading, error: previewError, requestPreview } = usePreview(300);
  const { config, updateConfig, resetConfig, warnings: configWarnings } = useConfig();
  const pm = usePresetMaterial();

  useEffect(() => {
    if (previewResult?.diagnostics?.face_oval && !faceOvalOverlayEnabled && !faceOvalPinned) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- syncing from external server diagnostics
      setFaceOval(previewResult.diagnostics.face_oval);
    }
  }, [previewResult, faceOvalOverlayEnabled, faceOvalPinned]);

  const vignetteParams = useMemo(() => getVignetteParams(config), [config]);

  const imageWidth = previewResult?.diagnostics.width ?? 0;
  const imageHeight = previewResult?.diagnostics.height ?? 0;

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

  useEffect(() => {
    return () => {
      if (originalUrl) URL.revokeObjectURL(originalUrl);
    };
  }, [originalUrl]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;
      if (e.key === "p" || e.key === "P" || e.key === "з" || e.key === "З") {
        e.preventDefault();
        setParamsCollapsed((prev) => !prev);
      }
      if (e.key === "[" || e.key === "х" || e.key === "Х") {
        e.preventDefault();
        setLeftColHidden((prev) => !prev);
      }
      if (e.key === "Escape" && compareMode) {
        e.preventDefault();
        setCompareMode(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [compareMode]);

  const requestPreviewWithOval = useCallback(
    (fid: string, mt: MachineType, cfg: ConfigTree) => {
      const oval = faceOvalOverlayEnabled ? faceOval : null;
      requestPreview(fid, mt, cfg, oval, profile);
    },
    [faceOvalOverlayEnabled, faceOval, requestPreview, profile],
  );

  const handleImageUploaded = useCallback(
    (newFileId: string, previewUrl: string) => {
      setFileId(newFileId);
      setOriginalUrl(previewUrl);
      setFaceOval({ ...DEFAULT_FACE_OVAL });
      setFaceOvalPinned(false);
      setDitherImageUrl(null);
      requestPreview(newFileId, pm.machineType, config, faceOvalOverlayEnabled ? faceOval : null, profile);
    },
    [pm.machineType, config, requestPreview, faceOvalOverlayEnabled, faceOval, profile],
  );

  const handleChangeImage = useCallback(() => {
    setFileId(null);
    setOriginalUrl(null);
    setFaceOval(null);
    setFaceOvalPinned(false);
    setDitherImageUrl(null);
  }, []);

  const handlePresetSelect = useCallback(
    (presetKey: string, presetConfig: ConfigTree, machineType: MachineType) => {
      pm.selectPreset(presetKey, presetConfig);
      const merged = deepMerge(config as Record<string, unknown>, presetConfig as Record<string, unknown>);
      if (!isConfigTree(merged)) return;
      updateConfig(merged);
      if (fileId) requestPreviewWithOval(fileId, machineType, merged);
    },
    [config, pm, updateConfig, fileId, requestPreviewWithOval],
  );

  const handleMaterialSelect = useCallback(
    async (mat: MaterialType, currentConfig?: ConfigTree): Promise<{ success: boolean; validationWarnings: string[] }> => {
      const result = await pm.selectMaterial(mat, currentConfig);
      if (result.success) {
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

  const handleResetParam = useCallback(
    (key: string) => {
      const baseline = pm.resetParam(key);
      if (baseline) {
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
    },
    [config, pm, updateConfig],
  );

  const handleFaceOvalChange = useCallback(
    (newOval: FaceOvalParams) => {
      setFaceOval(newOval);
      if (newOval.source === "manual" && !faceOvalPinned) {
        setFaceOvalPinned(true);
      }
      if (fileId) requestPreview(fileId, pm.machineType, config, newOval, profile);
    },
    [fileId, pm.machineType, config, requestPreview, faceOvalPinned, profile],
  );

  const handleFaceOvalPinToggle = useCallback(() => {
    setFaceOvalPinned((prev) => !prev);
  }, []);

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
      showToast(`Ошибка дизеринга: ${err instanceof Error ? err.message : err}`, { type: 'error', duration: 3000 });
    } finally {
      setDitherLoading(false);
    }
  }, [fileId, config, faceOvalOverlayEnabled, faceOval, previewResult, pm.machineType, showToast]);

  const availableSteps: Record<string, string> = useMemo(
    () => {
      if (!previewResult) return {};
      return { ...previewResult.images, ...(ditherImageUrl ? { dithered: ditherImageUrl } : {}) };
    },
    [previewResult, ditherImageUrl],
  );

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

  const stepLabel = STEP_LABELS[selectedStep] ?? selectedStep;

  const showFaceOval =
    faceOvalOverlayEnabled &&
    (selectedStep === "face_corrected" || selectedStep === "final") &&
    imageWidth > 0 &&
    imageHeight > 0 &&
    faceOval !== null;

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex flex-col">
      {backendDown && (
        <div className="bg-accent-orange/90 text-white px-6 py-2 text-sm font-medium text-center border-b border-accent-orange">
          <i className="ri-error-warning-line mr-1" />
          Backend не запущен. Запустите: <code className="bg-white/20 px-1 rounded-sm">make ui-backend</code>
        </div>
      )}

      <header className="flex items-center justify-between px-3 py-1.5 border-b border-border shrink-0 gap-3">
        <div className="flex items-center gap-4 min-w-0">
          <h1 className="text-xl font-heading font-semibold tracking-tight shrink-0">
            <i className="ri-brush-line mr-2 text-accent-blue" />
            Granite Retouch
          </h1>
          <MachineSelector
            groups={pm.catalogLoading ? [] : pm.groups}
            selectedPreset={pm.selectedPreset}
            machineType={pm.machineType}
            presetsCache={pm.presetsCache}
            onSelect={handlePresetSelect}
          />
          <ProfileSelector
            profile={profile}
            onChange={(p) => {
              setProfile(p);
              if (fileId) {
                const oval = faceOvalOverlayEnabled ? faceOval : null;
                requestPreview(fileId, pm.machineType, config, oval, p);
              }
            }}
          />
          {fileId && (
            <MaterialSelector
              material={pm.material}
              machineType={pm.machineType}
              profiles={pm.profiles}
              materialChanges={pm.materialChanges}
              validationWarnings={pm.validationWarnings}
              activeHint={pm.activeHint}
              onSelect={handleMaterialSelect}
              currentConfig={config}
              compact
            />
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {fileId && (
            <>
              <label className="flex items-center gap-1 text-xs text-text-muted cursor-pointer select-none whitespace-nowrap">
                <input
                  type="checkbox"
                  checked={!!(config?.vignette as any)?.enabled ?? true}
                  onChange={(e) => handleConfigChangeByPath(["vignette", "enabled"], e.target.checked ? 1 : 0)}
                  className="accent-accent-blue"
                />
                Виньетка
              </label>
              <div className="flex items-center gap-1">
                <label className="flex items-center gap-1 text-xs text-text-muted cursor-pointer select-none whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={faceOvalOverlayEnabled}
                    onChange={(e) => setFaceOvalOverlayEnabled(e.target.checked)}
                    className="accent-accent-orange"
                  />
                  Овал
                </label>
                <button
                  onClick={handleFaceOvalPinToggle}
                  className={`text-xs px-1 py-0.5 rounded transition-colors duration-200 ${
                    faceOvalPinned
                      ? "text-accent-orange"
                      : "text-text-muted hover:text-text-secondary"
                  }`}
                  title={
                    faceOvalPinned
                      ? "Открепить овал (автообновление)"
                      : "Закрепить овал (без автообновления)"
                  }
                >
                  <i className={faceOvalPinned ? "ri-pushpin-2-fill" : "ri-pushpin-2-line"} />
                </button>
              </div>
            </>
          )}
          <ExportButtons fileId={fileId} machineType={pm.machineType} config={config} faceOval={faceOval} processing={loading} profile={profile} />
        </div>
      </header>

      {comboPresets.length > 1 && (
        <div className="px-3 py-1.5 border-b border-border bg-bg-card/50">
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

      {configWarnings.length > 0 && (
        <div className="bg-accent-orange/10 text-accent-orange px-3 py-1.5 text-xs border-b border-accent-orange/20">
          {configWarnings.map((w, i) => (
            <span key={`warning-${i}`}>
              {i > 0 ? " · " : ""}{w}
            </span>
          ))}
        </div>
      )}

      {previewResult?.diagnostics && !previewResult.diagnostics.numba_available && (
        <div className="bg-accent-orange/10 text-accent-orange px-3 py-1.5 text-xs border-b border-accent-orange/20 flex items-center gap-2">
          <i className="ri-speed-line" />
          Дизеринг без Numba — медленно (30–120 сек). Установите: <code className="bg-accent-orange/20 px-1 rounded-sm">uv sync --extra fast</code>
        </div>
      )}

      {/* Step bar */}
      {fileId && (
        <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border bg-bg-card/50">
          <StepSelector
            selectedStep={selectedStep}
            onStepChange={setSelectedStep}
            availableSteps={Object.keys(availableSteps)}
            exportMode={getExportMode(config, pm.machineType)}
            onRequestDitherPreview={handleRequestDitherPreview}
            ditherLoading={ditherLoading}
          />
          <div className="border-l border-border pl-2 ml-auto">
            <button
              onClick={handleChangeImage}
              className="text-xs text-text-muted hover:text-text-secondary transition-colors duration-200 flex items-center gap-1"
            >
              <i className="ri-image-add-line" />
              Сменить фото
            </button>
          </div>
        </div>
      )}

      {/* Portrait Split: left-col + canvas */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left column */}
        <div
          className={`${
            leftColHidden ? "w-0 overflow-hidden border-r-0" : "w-left-col"
          } border-r border-border flex flex-col overflow-hidden transition-all duration-200`}
        >
          {!fileId ? (
            <ImageUpload onImageUploaded={handleImageUploaded} fullHeight />
          ) : (
            <>
              <div className="flex-1 min-h-0 overflow-hidden p-3">
                <BeforeImage originalUrl={originalUrl} />
              </div>

              <div
                className={`flex-shrink-0 overflow-hidden border-t border-border transition-all duration-300 ${
                  paramsCollapsed ? "max-h-0 opacity-0" : "max-h-[60vh] opacity-100"
                }`}
              >
                <div className="p-3 overflow-y-auto max-h-[60vh]">
                  <ParamsPanel
                    machineType={pm.machineType}
                    config={config}
                    onConfigChange={handleConfigChangeByPath}
                    overriddenKeys={pm.overriddenKeys}
                    onResetParam={handleResetParam}
                  />
                </div>
              </div>

              <div className="flex-shrink-0 border-t border-border px-3 py-1.5 flex items-center justify-between bg-bg-card/50">
                <button
                  onClick={() => setParamsCollapsed((prev) => !prev)}
                  className="text-xs text-text-muted hover:text-text-secondary transition-colors duration-200 flex items-center gap-1"
                >
                  <i className={`ri-arrow-${paramsCollapsed ? "down" : "up"}-s-line`} />
                  Параметры
                </button>
              </div>

              <div className="flex-shrink-0 border-t border-border p-3 space-y-2 bg-bg-card/50">
                <ConfigActions
                  config={config}
                  presetsCache={pm.presetsCache}
                  onConfigReset={handleReset}
                  onConfigChange={handleConfigChangeFull}
                />
                <DiagnosticsPanel
                  compact
                  diagnostics={previewResult?.diagnostics ?? null}
                  warnings={previewResult?.warnings ?? []}
                />
                {profile === "diagnostic" && (
                  <StepMetricsPanel
                    stepMetrics={previewResult?.diagnostics?.step_metrics}
                  />
                )}
              </div>
            </>
          )}
        </div>

        <main className="flex-1 bg-canvas relative flex flex-col overflow-hidden">
          {leftColHidden && !compareMode && (
            <button
              onClick={() => setLeftColHidden(false)}
              className="absolute left-0 top-1/2 -translate-y-1/2 z-10 w-5 h-10 bg-bg-card/80 hover:bg-bg-card border border-border border-l-0 rounded-r flex items-center justify-center text-text-muted hover:text-text-secondary transition-colors duration-200"
              title="Показать панель ([/Х)"
            >
              <i className="ri-arrow-right-s-line text-sm" />
            </button>
          )}

          {!loading && !previewError && previewResult && !compareMode && (
            <div className="absolute top-2 right-2 z-10 flex gap-2">
              <button
                onClick={() => setCompareMode(true)}
                className="text-xs px-2 py-1 rounded bg-black/50 text-text-muted hover:text-text-secondary hover:bg-black/60 transition-colors duration-200 flex items-center gap-1"
                title="Сравнить оригинал и результат"
              >
                <i className="ri-side-bar-line" />
                Сравнить
              </button>
            </div>
          )}

          {!loading && previewError && (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-accent-red text-sm">
                <i className="ri-error-warning-line mr-1" />
                {previewError}
              </p>
            </div>
          )}
          {!previewError && previewResult && !compareMode && (
            <div className="relative flex-1">
              <AfterImage
                imageUrl={availableSteps[selectedStep] ?? null}
                stepLabel={stepLabel}
                faceOvalOverlayEnabled={showFaceOval}
                faceOval={faceOval}
                onFaceOvalChange={handleFaceOvalChange}
                imageWidth={imageWidth}
                imageHeight={imageHeight}
                vignetteParams={vignetteParams}
                onVignetteParamChange={handleConfigChangeByPath}
              />
              {loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-bg-canvas/50 text-text-muted gap-2 z-10">
                  <i className="ri-loader-4-line animate-spin text-xl" />
                  <span>Обработка...</span>
                </div>
              )}
            </div>
          )}
          {!previewError && previewResult && compareMode && (
            <div className="relative flex-1 flex overflow-hidden">
              <div className="flex-1 min-w-0 overflow-hidden p-2">
                <BeforeImage originalUrl={originalUrl} />
              </div>
              <div className="w-px bg-border flex-shrink-0" />
              <div className="flex-1 min-w-0 overflow-hidden p-2">
                <AfterImage
                  imageUrl={availableSteps[selectedStep] ?? null}
                  stepLabel={stepLabel}
                  faceOvalOverlayEnabled={showFaceOval}
                  faceOval={faceOval}
                  onFaceOvalChange={handleFaceOvalChange}
                  imageWidth={imageWidth}
                  imageHeight={imageHeight}
                  vignetteParams={vignetteParams}
                  onVignetteParamChange={handleConfigChangeByPath}
                />
              </div>
              <button
                onClick={() => setCompareMode(false)}
                className="absolute top-2 right-2 z-10 text-xs px-2 py-1 rounded bg-black/50 text-text-muted hover:text-text-secondary hover:bg-black/60 transition-colors duration-200 flex items-center gap-1"
                title="Закрыть сравнение (Escape)"
              >
                <i className="ri-close-line" />
                Закрыть
              </button>
              {loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-bg-canvas/50 text-text-muted gap-2 z-10">
                  <i className="ri-loader-4-line animate-spin text-xl" />
                  <span>Обработка...</span>
                </div>
              )}
            </div>
          )}
          {loading && !previewResult && (
            <div className="flex-1 flex items-center justify-center text-text-muted gap-2">
              <i className="ri-loader-4-line animate-spin text-xl" />
              <span>Обработка...</span>
            </div>
          )}
          {!loading && !previewError && !previewResult && !fileId && (
            <div className="flex-1 flex items-center justify-center text-text-muted">
              <div className="text-center space-y-3">
                <i className="ri-image-line text-5xl text-text-muted/30" />
                <p className="text-text-secondary">Загрузите изображение для обработки</p>
                <p className="text-text-muted text-xs">PNG, TIFF, BMP — перетащите в панель слева или нажмите для выбора</p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
