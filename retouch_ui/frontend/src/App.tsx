import { useState, useCallback } from "react";
import { ImageUpload } from "./components/image-upload";
import { BeforeAfter } from "./components/before-after";
import { StepSelector } from "./components/step-selector";
import { ParamsPanel } from "./components/params-panel";
import { MachineSwitch } from "./components/machine-switch";
import { DiagnosticsPanel } from "./components/diagnostics-panel";
import { ConfigActions } from "./components/config-actions";
import { ExportButtons } from "./components/export-buttons";
import { usePreview } from "./hooks/use-preview";
import { useConfig } from "./hooks/use-config";

export default function App() {
  // State
  const [fileId, setFileId] = useState<string | null>(null);
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);
  const [machineType, setMachineType] = useState<"laser" | "impact">("laser");
  const [selectedStep, setSelectedStep] = useState("final");

  // Hooks
  const { result: previewResult, loading, error: previewError, requestPreview } = usePreview(300);
  const { config, updateConfig, resetConfig, warnings: configWarnings } = useConfig();

  // Handlers
  const handleImageUploaded = useCallback(
    (newFileId: string, previewUrl: string) => {
      setFileId(newFileId);
      setOriginalUrl(previewUrl);
      // Auto-preview after upload
      requestPreview(newFileId, machineType, config);
    },
    [machineType, config, requestPreview],
  );

  const handleMachineChange = useCallback(
    (type: "laser" | "impact") => {
      setMachineType(type);
      if (fileId) requestPreview(fileId, type, config);
    },
    [fileId, config, requestPreview],
  );

  const handleConfigChangeByPath = useCallback(
    (path: string[], value: number) => {
      const newConfig = JSON.parse(JSON.stringify(config));
      let obj: Record<string, any> = newConfig;
      for (let i = 0; i < path.length - 1; i++) {
        if (!obj[path[i]]) obj[path[i]] = {};
        obj = obj[path[i]];
      }
      obj[path[path.length - 1]] = value;
      updateConfig(newConfig);
      if (fileId) requestPreview(fileId, machineType, newConfig);
    },
    [config, fileId, machineType, updateConfig, requestPreview],
  );

  const handleConfigChangeFull = useCallback(
    (newConfig: Record<string, any>) => {
      updateConfig(newConfig);
      if (fileId) requestPreview(fileId, machineType, newConfig);
    },
    [fileId, machineType, updateConfig, requestPreview],
  );

  const handleReset = useCallback(
    (defaults: Record<string, any>) => {
      resetConfig(defaults);
      if (fileId) requestPreview(fileId, machineType, defaults);
    },
    [fileId, machineType, resetConfig, requestPreview],
  );

  // Layout: sidebar left (params) + main area (image) right
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border shrink-0">
        <h1 className="text-xl font-heading font-semibold tracking-tight">
          <i className="ri-brush-line mr-2 text-accent-blue" />
          Granite Retouch
        </h1>
        <div className="flex gap-4 items-center">
          <MachineSwitch value={machineType} onChange={handleMachineChange} />
          <ExportButtons fileId={fileId} machineType={machineType} config={config} />
        </div>
      </header>

      {/* Config warnings banner */}
      {configWarnings.length > 0 && (
        <div className="bg-accent-orange/10 text-accent-orange px-6 py-2 text-sm border-b border-accent-orange/20">
          {configWarnings.map((w, i) => (
            <span key={i}>
              {i > 0 ? " · " : ""}{w}
            </span>
          ))}
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
              <ParamsPanel
                machineType={machineType}
                config={config}
                onConfigChange={handleConfigChangeByPath}
              />
              <div className="border-t border-border pt-4">
                <ConfigActions
                  config={config}
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
                availableSteps={Object.keys(previewResult.images)}
              />
              <BeforeAfter
                originalUrl={originalUrl}
                images={previewResult.images}
                selectedStep={selectedStep}
                onStepChange={setSelectedStep}
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
    </div>
  );
}
