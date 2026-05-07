import { useState, useEffect, useCallback } from "react";
import { saveConfig, fetchDefaults, fetchPresets, createPreset, deletePreset } from "../lib/api";
import type { PresetItem } from "../lib/api";

interface Props {
  config: Record<string, any>;
  onConfigReset: (defaults: Record<string, any>) => void;
  onConfigChange: (config: Record<string, any>) => void;
}

export function ConfigActions({ config, onConfigReset, onConfigChange }: Props) {
  const [presets, setPresets] = useState<PresetItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [presetName, setPresetName] = useState("");
  const [showPresets, setShowPresets] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchPresets()
      .then((res) => setPresets(res.presets))
      .catch(() => {});
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveMessage(null);
    try {
      await saveConfig(config);
      setSaveMessage("Сохранено");
      setTimeout(() => setSaveMessage(null), 2000);
    } catch {
      setSaveMessage("Ошибка сохранения");
    } finally {
      setSaving(false);
    }
  }, [config]);

  const handleReset = useCallback(async () => {
    try {
      const result = await fetchDefaults();
      onConfigReset(result.defaults);
    } catch {
      // Ignore if backend is down
    }
  }, [onConfigReset]);

  const handleCreatePreset = useCallback(async () => {
    if (!presetName.trim()) return;
    try {
      await createPreset(presetName, config);
      setPresetName("");
      const res = await fetchPresets();
      setPresets(res.presets);
    } catch {
      // Ignore errors
    }
  }, [presetName, config]);

  const handleDeletePreset = useCallback(async (name: string) => {
    try {
      await deletePreset(name);
      setPresets((prev) => prev.filter((p) => p.name !== name));
    } catch {
      // Ignore errors
    }
  }, []);

  return (
    <div className="space-y-3">
      {/* Save / Reset */}
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 px-3 py-2 bg-accent-blue text-white rounded text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {saving ? "Сохранение..." : "Сохранить config.yaml"}
        </button>
        <button
          onClick={handleReset}
          className="px-3 py-2 bg-bg-card text-text-secondary rounded text-sm hover:bg-bg-hover transition-colors"
        >
          Сброс
        </button>
      </div>

      {saveMessage && (
        <p className="text-xs text-accent-green">{saveMessage}</p>
      )}

      {/* Presets toggle */}
      <button
        onClick={() => setShowPresets(!showPresets)}
        className="w-full text-left text-sm text-text-muted hover:text-text-secondary transition-colors flex items-center justify-between"
      >
        <span>Пресеты ({presets.length})</span>
        <i className={`ri-arrow-down-s-line transition-transform ${showPresets ? "rotate-180" : ""}`} />
      </button>

      {/* Presets list */}
      {showPresets && (
        <div className="space-y-2">
          {presets.length === 0 && (
            <p className="text-text-muted text-xs">Нет сохранённых пресетов</p>
          )}
          {presets.map((p) => (
            <div key={p.name} className="flex items-center gap-2">
              <button
                onClick={() => onConfigChange(p.config)}
                className="flex-1 text-left px-2 py-1.5 text-sm bg-bg-card rounded hover:bg-bg-hover transition-colors text-text-secondary"
              >
                {p.name}
              </button>
              <button
                onClick={() => handleDeletePreset(p.name)}
                className="text-accent-red text-xs hover:underline px-1"
                title="Удалить пресет"
              >
                <i className="ri-delete-bin-line" />
              </button>
            </div>
          ))}

          {/* Create preset */}
          <div className="flex gap-1 pt-1">
            <input
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder="Имя пресета"
              className="flex-1 bg-bg-input text-sm px-2 py-1.5 rounded text-text-primary"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreatePreset();
              }}
            />
            <button
              onClick={handleCreatePreset}
              className="px-2 py-1.5 text-sm bg-bg-card rounded hover:bg-bg-hover transition-colors text-text-secondary"
              title="Создать пресет"
            >
              <i className="ri-add-line" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
