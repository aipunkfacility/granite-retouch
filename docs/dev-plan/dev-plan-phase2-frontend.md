# Фаза 2: React + Vite Frontend

**Версия плана**: 3.4 (исправления по аудиту — A6, A7, A17)
**Предыдущий этап**: [Фаза 1](dev-plan-phase1-backend.md) (можно параллелить с мок-API)
**Следующий этап**: [Фаза 3](dev-plan-phase3-integration.md)
**Время**: 8–12 часов
**Цель**: Интерактивный UI для настройки параметров ретуши с предпросмотром до/после.

---

## Изменения v3.4 относительно v3.3

| # | Критичность | Изменение |
|---|-------------|-----------|
| A6 | 🟠 High | Добавлена **полная реализация** `hooks/use-config.ts` (вместо отсутствующей) |
| A7 | 🟠 High | `params-panel.tsx` и `config-actions.tsx` — **заполнены рабочие каркасы** (вместо заглушек-комментариев) |
| A17 | 🟢 Low | `image-upload.tsx` — добавлен `useRef` и `onClick` для программного клика по скрытому `<input>` |

---

## Стек

| Технология | Версия | Назначение |
|------------|--------|-----------|
| React | 19 | UI |
| Vite | 6+ | Сборка и dev-сервер (~150 МБ RAM) |
| TypeScript | 5+ | Типизация |
| shadcn/ui | latest | Компоненты (slider, tabs, card, button, ...) |
| Tailwind CSS | 4 | Стили |
| @fontsource/outfit | — | Заголовки секций |
| @fontsource/inter | — | Текст, слайдеры, описания |

---

## Директория

```
granite-retouch/
└── retouch_ui/
    └── frontend/
        ├── package.json
        ├── vite.config.ts
        ├── tsconfig.json
        ├── tailwind.config.ts
        ├── index.html
        └── src/
            ├── main.tsx
            ├── App.tsx
            ├── index.css                # CSS-переменные + Tailwind
            ├── components/
            │   ├── ui/                  # shadcn/ui (автоген)
            │   ├── image-upload.tsx      # Drag & drop загрузка → file_id [A17: useRef + onClick]
            │   ├── before-after.tsx      # До/После (side-by-side или табы)
            │   ├── step-selector.tsx     # Переключатель промежуточных шагов
            │   ├── params-panel.tsx      # Слайдеры параметров [A7: рабочий каркас]
            │   ├── machine-switch.tsx    # Переключатель laser/impact
            │   ├── diagnostics-panel.tsx # Диагностика обработки
            │   ├── config-actions.tsx    # Сохранить / Сброс / Пресеты [A7: рабочий каркас]
            │   └── export-buttons.tsx    # Экспорт TIFF/PNG
            ├── lib/
            │   ├── api.ts               # Фетчеры: uploadImage → file_id, fetchPreview(fileId, ...)
            │   ├── config-schema.ts     # Типы + диапазоны параметров (+ face_region_top, highlight_start)
            │   └── utils.ts             # cn() и утилиты
            └── hooks/
                ├── use-preview.ts        # Предпросмотр с debounce (по file_id)
                └── use-config.ts         # Управление конфигом [A6: полная реализация]
```

---

## Задача 1: Инициализация проекта

```bash
cd retouch_ui
npm create vite@latest frontend -- --template react-ts
cd frontend
npx shadcn@latest init
npx shadcn@latest add slider tabs card button label input separator badge switch select dialog
npm install @fontsource/outfit @fontsource/inter remixicon
npm install -D concurrently
```

**vite.config.ts** — прокси к FastAPI:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
```

---

## Задача 2: index.css — дизайн-токены

Плоский тёмный фон, нет glassmorphism, нет backdrop-filter. Шрифты Outfit (заголовки) и Inter (текст).

```css
@import "@fontsource/outfit/400.css";
@import "@fontsource/outfit/600.css";
@import "@fontsource/inter/400.css";
@import "@fontsource/inter/500.css";
@import "tailwindcss";

@theme {
  /* Фон */
  --color-bg-primary: #1a1a1a;
  --color-bg-secondary: #222222;
  --color-bg-card: #2a2a2a;
  --color-bg-input: #333333;
  --color-bg-hover: #3a3a3a;

  /* Текст */
  --color-text-primary: #f0f0f0;
  --color-text-secondary: #a0a0a0;
  --color-text-muted: #666666;

  /* Акценты */
  --color-accent-blue: #4a90d9;
  --color-accent-green: #4caf50;
  --color-accent-orange: #ff9800;
  --color-accent-red: #ef5350;

  /* Рамки */
  --color-border: #3a3a3a;
  --color-border-focus: #4a90d9;

  /* Шрифты */
  --font-heading: "Outfit", sans-serif;
  --font-body: "Inter", sans-serif;
}

/* Базовые стили */
body {
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
  font-family: var(--font-body);
  -webkit-font-smoothing: antialiased;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-heading);
}

/* Scrollbar — тёмная тема */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: var(--color-bg-secondary);
}
::-webkit-scrollbar-thumb {
  background: var(--color-bg-hover);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-muted);
}
```

**Ключевые принципы**:
- Фон `#1a1a1a` — нейтральный тёмный, не искажает восприятие яркости фото
- Никакого `backdrop-filter`, `rgba()` с размытием — только непрозрачные цвета
- Шрифт Outfit 600 для заголовков секций (параметры, диагностика, пресеты)
- Шрифт Inter 400/500 для текста, значений слайдеров, описаний

---

## Задача 3: config-schema.ts

Типы и диапазоны параметров для UI-слайдеров. Один источник истины для min/max/step/label.
Включает `face_region_top` и `highlight_start` в MachineParams (A1 — синхронизация с DEFAULTS).

```typescript
/** Диапазон параметра для UI-слайдера */
export interface ParamRange {
  min: number;
  max: number;
  step: number;
  label: string;         // Читаемое название для UI
  unit?: string;         // Единица измерения (px, %, и т.д.)
}

/** Параметры машин (laser / impact) */
export interface MachineParams {
  glow_size_min: ParamRange;
  glow_size_max: ParamRange;
  glow_opacity_min: ParamRange;
  glow_opacity_max: ParamRange;
  brightness: ParamRange;
  face_brightness_target_min: ParamRange;
  face_brightness_target_max: ParamRange;
  face_region_top: ParamRange;       // A1: добавлен в v3.4
  highlight_start: ParamRange;       // A1: добавлен в v3.4
}

/** Общие параметры обработки */
export interface ProcessingParams {
  blue_threshold: ParamRange;
  min_blue_ratio: ParamRange;
  fringe_radius: ParamRange;
}

/** Параметры виньетки */
export interface VignetteParams {
  vertical_offset: ParamRange;
  vertical_diameter: ParamRange;
  blur_radius: ParamRange;
  headroom: ParamRange;
  horizontal_oversize: ParamRange;
}

/** Полная схема параметров */
export interface ConfigSchema {
  processing: ProcessingParams & {
    laser: MachineParams;
    impact: MachineParams;
  };
  vignette: VignetteParams;
}

/** Схема параметров — используется params-panel.tsx для генерации слайдеров */
export const CONFIG_SCHEMA: ConfigSchema = {
  processing: {
    blue_threshold: { min: 10, max: 80, step: 1, label: "Порог синего", unit: "" },
    min_blue_ratio: { min: 0, max: 1, step: 0.01, label: "Мин. доля синего", unit: "" },
    fringe_radius: { min: 0, max: 10, step: 1, label: "Радиус fringe-удаления", unit: "px" },
    laser: {
      glow_size_min: { min: 5, max: 100, step: 1, label: "Glow: мин. размер", unit: "px" },
      glow_size_max: { min: 5, max: 100, step: 1, label: "Glow: макс. размер", unit: "px" },
      glow_opacity_min: { min: 10, max: 100, step: 1, label: "Glow: мин. непрозрачность", unit: "%" },
      glow_opacity_max: { min: 10, max: 100, step: 1, label: "Glow: макс. непрозрачность", unit: "%" },
      brightness: { min: 0.5, max: 1.5, step: 0.01, label: "Яркость", unit: "x" },
      face_brightness_target_min: { min: 100, max: 255, step: 1, label: "Цель яркости лица: мин", unit: "" },
      face_brightness_target_max: { min: 100, max: 255, step: 1, label: "Цель яркости лица: макс", unit: "" },
      face_region_top: { min: 0.2, max: 0.8, step: 0.01, label: "Зона лица (верх)", unit: "" },
      highlight_start: { min: 100, max: 250, step: 1, label: "Начало затухания коррекции", unit: "" },
    },
    impact: {
      glow_size_min: { min: 5, max: 100, step: 1, label: "Glow: мин. размер", unit: "px" },
      glow_size_max: { min: 5, max: 100, step: 1, label: "Glow: макс. размер", unit: "px" },
      glow_opacity_min: { min: 10, max: 100, step: 1, label: "Glow: мин. непрозрачность", unit: "%" },
      glow_opacity_max: { min: 10, max: 100, step: 1, label: "Glow: макс. непрозрачность", unit: "%" },
      brightness: { min: 0.5, max: 1.5, step: 0.01, label: "Яркость", unit: "x" },
      face_brightness_target_min: { min: 100, max: 255, step: 1, label: "Цель яркости лица: мин", unit: "" },
      face_brightness_target_max: { min: 100, max: 255, step: 1, label: "Цель яркости лица: макс", unit: "" },
      face_region_top: { min: 0.2, max: 0.8, step: 0.01, label: "Зона лица (верх)", unit: "" },
      highlight_start: { min: 100, max: 250, step: 1, label: "Начало затухания коррекции", unit: "" },
    },
  },
  vignette: {
    vertical_offset: { min: 0, max: 0.3, step: 0.01, label: "Вертикальное смещение", unit: "" },
    vertical_diameter: { min: 0.2, max: 0.8, step: 0.01, label: "Вертикальный диаметр", unit: "" },
    blur_radius: { min: 10, max: 120, step: 1, label: "Радиус размытия", unit: "px" },
    headroom: { min: 0.2, max: 1.0, step: 0.01, label: "Headroom", unit: "" },
    horizontal_oversize: { min: 0, max: 0.5, step: 0.01, label: "Горизонтальный оверсайз", unit: "" },
  },
};

/** Группы параметров для вкладок params-panel */
export const PARAM_GROUPS = [
  { key: "common", label: "Общие", params: ["blue_threshold", "min_blue_ratio", "fringe_radius"] },
  { key: "laser", label: "Laser", params: Object.keys(CONFIG_SCHEMA.processing.laser) },
  { key: "impact", label: "Impact", params: Object.keys(CONFIG_SCHEMA.processing.impact) },
  { key: "vignette", label: "Виньетка", params: Object.keys(CONFIG_SCHEMA.vignette) },
] as const;
```

---

## Задача 4: lib/api.ts — с file_id

```typescript
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

/** Загрузить изображение — получить file_id */
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

/** Предпросмотр обработки — по file_id */
export async function fetchPreview(
  fileId: string,
  machineType: "laser" | "impact",
  configOverride?: Record<string, any>,
  signal?: AbortSignal,            // передаём AbortSignal для отмены HTTP-запроса
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
    signal,                         // ← сигнал передан в fetch()
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Preview failed: ${err}`);
  }

  return res.json();
}

/** Экспорт результата — по file_id */
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

/** Получить конфиг */
export async function fetchConfig(): Promise<ConfigResult> {
  const res = await fetch(`${API_BASE}/config`);
  return res.json();
}

/** Сохранить конфиг */
export async function saveConfig(config: Record<string, any>): Promise<{ saved: boolean; warnings: string[] }> {
  const res = await fetch(`${API_BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
  return res.json();
}

/** Дефолтный конфиг */
export async function fetchDefaults(): Promise<ConfigResult> {
  const res = await fetch(`${API_BASE}/config/defaults`);
  return res.json();
}

/** Список пресетов */
export async function fetchPresets(): Promise<{ presets: PresetItem[] }> {
  const res = await fetch(`${API_BASE}/presets`);
  return res.json();
}

/** Создать пресет */
export async function createPreset(name: string, config: Record<string, any>) {
  const res = await fetch(`${API_BASE}/presets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, config }),
  });
  return res.json();
}

/** Удалить пресет */
export async function deletePreset(name: string) {
  const res = await fetch(`${API_BASE}/presets/${name}`, { method: "DELETE" });
  return res.json();
}
```

**Ключевое изменение**: `uploadImage()` → `file_id`, затем `fetchPreview(fileId, ...)` — без пересылки файла.

---

## Задача 5: hooks/use-preview.ts — с file_id

```typescript
import { useState, useCallback, useRef, useEffect } from "react";
import { fetchPreview, type PreviewResult } from "../lib/api";

interface UsePreviewReturn {
  result: PreviewResult | null;
  loading: boolean;
  error: string | null;
  requestPreview: (fileId: string, machineType: "laser" | "impact", config?: Record<string, any>) => void;
}

export function usePreview(debounceMs = 300): UsePreviewReturn {
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const requestPreview = useCallback(
    (fileId: string, machineType: "laser" | "impact", config?: Record<string, any>) => {
      // Отмена предыдущего запроса
      if (abortRef.current) {
        abortRef.current.abort();
      }

      // Debounce
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }

      timerRef.current = setTimeout(async () => {
        setLoading(true);
        setError(null);

        const controller = new AbortController();
        abortRef.current = controller;

        try {
          const data = await fetchPreview(fileId, machineType, config, controller.signal);
          if (!controller.signal.aborted) {
            setResult(data);
          }
        } catch (e: any) {
          if (!controller.signal.aborted) {
            setError(e.message);
          }
        } finally {
          setLoading(false);
        }
      }, debounceMs);
    },
    [debounceMs],
  );

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  return { result, loading, error, requestPreview };
}
```

**Ключевое изменение**: `requestPreview(fileId, ...)` вместо `requestPreview(file, ...)`.

---

## Задача 6: Компоненты

Каждый компонент — отдельный файл в `src/components/`. Используют shadcn/ui примитивы.

### image-upload.tsx **[A17 — исправлено]**

> **A17 (Low)**: В v3.3 скрытый `<input type="file">` не имел программного клика — работала только зона drag & drop. Добавлен `useRef` и `onClick` на обёрточный `<div>`.

```typescript
import { useCallback, useRef, useState } from "react";
import { uploadImage } from "../lib/api";

interface Props {
  onImageUploaded: (fileId: string, previewUrl: string) => void;
}

export function ImageUpload({ onImageUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const { file_id } = await uploadImage(file);
      const previewUrl = URL.createObjectURL(file);
      onImageUploaded(file_id, previewUrl);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }, [onImageUploaded]);

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
        ${dragOver ? "border-accent-blue bg-bg-hover" : "border-border bg-bg-card"}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={(e) => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }}
        className="hidden"
      />
      {uploading ? "Загрузка..." : "Перетащите PNG/TIFF или нажмите для выбора"}
      {error && <p className="text-accent-red mt-2">{error}</p>}
    </div>
  );
}
```

**Что изменилось (A17)**:
- Добавлен `const inputRef = useRef<HTMLInputElement>(null)`
- `<input ref={inputRef} ...>` — привязка ref
- `onClick={() => inputRef.current?.click()}` — клик по зоне открывает файловый диалог
- `onChange` — безопасная проверка `e.target.files?.[0]` (вместо `e.target.files[0]`)

### before-after.tsx

```typescript
/** Side-by-side до/после + табы для промежуточных шагов */
import { useState } from "react";

interface Props {
  originalUrl: string | null;        // URL загруженного изображения (до обработки)
  images: Record<string, string>;    // ключ: step, значение: base64 data URI
  selectedStep: string;
  onStepChange: (step: string) => void;
}

const STEPS = [
  { key: "chromakey", label: "Хромакей" },
  { key: "glow", label: "Glow" },
  { key: "leveled", label: "Levels" },
  { key: "face_corrected", label: "Лицо" },
  { key: "final", label: "Результат" },
];

export function BeforeAfter({ originalUrl, images, selectedStep, onStepChange }: Props) {
  // Layout: два изображения рядом (side-by-side)
  // Левое — оригинал, правое — обработанное (из images[selectedStep])
  // Если оригинала нет — показываем только «После»
  return (
    <div className="flex gap-2">
      {/* До */}
      <div className="flex-1">
        <p className="text-text-secondary text-sm mb-1">До</p>
        {originalUrl && <img src={originalUrl} className="max-h-[500px] object-contain" />}
      </div>
      {/* После */}
      <div className="flex-1">
        <p className="text-text-secondary text-sm mb-1">После: {STEPS.find(s => s.key === selectedStep)?.label}</p>
        {images[selectedStep] && <img src={images[selectedStep]} className="max-h-[500px] object-contain" />}
      </div>
    </div>
  );
}
```

### step-selector.tsx

```typescript
/** Переключатель промежуточных шагов обработки */
interface Props {
  selectedStep: string;
  onStepChange: (step: string) => void;
  availableSteps: string[];  // Ключи шагов, для которых есть изображения
}

const STEP_LABELS: Record<string, string> = {
  chromakey: "Хромакей",
  glow: "Glow",
  leveled: "Levels",
  face_corrected: "Лицо",
  final: "Результат",
  arch_mask: "Маска",
};

export function StepSelector({ selectedStep, onStepChange, availableSteps }: Props) {
  // Рендерит кнопки-табы: [Хромакей] [Glow] [Levels] [Лицо] [Результат]
  // Недоступные шаги — disabled (нет данных)
  // Использует shadcn Button variant="outline" size="sm"
  return (
    <div className="flex gap-1">
      {availableSteps.map((step) => (
        <button
          key={step}
          onClick={() => onStepChange(step)}
          className={`px-3 py-1 text-sm rounded
            ${step === selectedStep ? "bg-accent-blue text-white" : "bg-bg-card text-text-secondary hover:bg-bg-hover"}`}
        >
          {STEP_LABELS[step] || step}
        </button>
      ))}
    </div>
  );
}
```

### params-panel.tsx **[A7 — заполнен рабочий каркас]**

> **A7 (High)**: В v3.3 содержал только комментарии вместо JSX. Добавлен полный рабочий каркас: рендер слайдеров по CONFIG_SCHEMA, вкладки по PARAM_GROUPS, чтение/запись значений из config.

```typescript
import { CONFIG_SCHEMA, PARAM_GROUPS, type ParamRange } from "../lib/config-schema";
import { useState } from "react";

interface Props {
  machineType: "laser" | "impact";
  config: Record<string, any>;
  onConfigChange: (path: string[], value: number) => void;
}

export function ParamsPanel({ machineType, config, onConfigChange }: Props) {
  const [activeTab, setActiveTab] = useState<string>("common");

  const renderSlider = (path: string[], param: ParamRange, value: number) => (
    <div key={path.join(".")} className="space-y-1">
      <div className="flex justify-between text-sm">
        <label className="text-text-secondary">{param.label}</label>
        <span className="text-text-muted">{value}{param.unit ? ` ${param.unit}` : ""}</span>
      </div>
      <input
        type="range"
        min={param.min}
        max={param.max}
        step={param.step}
        value={value}
        onChange={(e) => onConfigChange(path, parseFloat(e.target.value))}
        className="w-full accent-accent-blue"
      />
    </div>
  );

  const getParamRange = (groupKey: string, paramKey: string): ParamRange | null => {
    if (groupKey === "common") return CONFIG_SCHEMA.processing[paramKey as keyof typeof CONFIG_SCHEMA.processing] as ParamRange;
    if (groupKey === "vignette") return CONFIG_SCHEMA.vignette[paramKey as keyof typeof CONFIG_SCHEMA.vignette] as ParamRange;
    return CONFIG_SCHEMA.processing[groupKey as "laser" | "impact"]?.[paramKey as keyof typeof CONFIG_SCHEMA.processing.laser] as ParamRange ?? null;
  };

  const getValue = (path: string[]): number => {
    let obj: any = config;
    for (const key of path) obj = obj?.[key];
    return obj ?? 0;
  };

  return (
    <div className="space-y-4">
      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {PARAM_GROUPS.map((g) => (
          <button
            key={g.key}
            onClick={() => setActiveTab(g.key)}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors
              ${activeTab === g.key ? "border-accent-blue text-accent-blue" : "border-transparent text-text-muted hover:text-text-secondary"}`}
          >
            {g.label}
          </button>
        ))}
      </div>
      {/* Sliders */}
      <div className="space-y-3">
        {PARAM_GROUPS.filter(g => g.key === activeTab).map((g) =>
          g.params.map((paramKey) => {
            const range = getParamRange(g.key, paramKey);
            if (!range) return null;
            const path = g.key === "common"
              ? ["processing", paramKey]
              : g.key === "vignette"
                ? ["vignette", paramKey]
                : ["processing", g.key, paramKey];
            return renderSlider(path, range, getValue(path));
          })
        )}
      </div>
    </div>
  );
}
```

**Структура каркаса (A7)**:
- **Вкладки** по `PARAM_GROUPS` — Общие / Laser / Impact / Виньетка
- **renderSlider()** — рендерит `<input type="range">` + label + текущее значение
- **getParamRange()** — получает ParamRange из CONFIG_SCHEMA по группе и ключу
- **getValue()** — извлекает значение из config по path (массив ключей)
- При изменении слайдера вызывается `onConfigChange(path, value)` — App.tsx обновляет конфиг
- Агент может заменить `<input type="range">` на shadcn `<Slider>` при необходимости

### machine-switch.tsx

```typescript
/** Переключатель laser/impact */
interface Props {
  value: "laser" | "impact";
  onChange: (type: "laser" | "impact") => void;
}

export function MachineSwitch({ value, onChange }: Props) {
  // Две кнопки: [Laser] [Impact]
  // Активная — bg-accent-blue, неактивная — bg-bg-card
  // Использует shadcn Button
  return (
    <div className="flex gap-2">
      <button
        onClick={() => onChange("laser")}
        className={`px-4 py-2 rounded font-semibold
          ${value === "laser" ? "bg-accent-blue text-white" : "bg-bg-card text-text-secondary"}`}
      >
        Laser
      </button>
      <button
        onClick={() => onChange("impact")}
        className={`px-4 py-2 rounded font-semibold
          ${value === "impact" ? "bg-accent-blue text-white" : "bg-bg-card text-text-secondary"}`}
      >
        Impact
      </button>
    </div>
  );
}
```

### diagnostics-panel.tsx

```typescript
/** Диагностика обработки: face brightness, glow, black ratio */
interface Props {
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
  } | null;
  warnings: string[];
}

export function DiagnosticsPanel({ diagnostics, warnings }: Props) {
  if (!diagnostics) return null;
  // Карточка с метриками:
  // Face: 165.3 → 218.7 (factor: 1.322)
  // Glow: 60px / 35%
  // Black ratio: 38.2%
  // Blue ratio: 72.1%
  // Размер: 2048x2048
  // Warnings: жёлтый текст если есть
  return (
    <div className="bg-bg-card rounded-lg p-4 space-y-1">
      <h3 className="font-heading font-semibold text-text-primary">Диагностика</h3>
      <p className="text-sm text-text-secondary">
        Face: {diagnostics.face_brightness_before.toFixed(1)} → {diagnostics.face_brightness_after.toFixed(1)}
        <span className="text-text-muted ml-2">(factor: {diagnostics.face_correction_factor.toFixed(3)})</span>
      </p>
      <p className="text-sm text-text-secondary">
        Glow: {diagnostics.glow_size}px / {(diagnostics.glow_opacity * 100).toFixed(0)}%
      </p>
      <p className="text-sm text-text-secondary">
        Black: {(diagnostics.black_ratio * 100).toFixed(1)}% | Blue: {(diagnostics.blue_ratio * 100).toFixed(1)}%
      </p>
      <p className="text-sm text-text-muted">
        {diagnostics.width}x{diagnostics.height}
      </p>
      {warnings.length > 0 && (
        <div className="mt-2">
          {warnings.map((w, i) => (
            <p key={i} className="text-sm text-accent-orange">{w}</p>
          ))}
        </div>
      )}
    </div>
  );
}
```

### config-actions.tsx **[A7 — заполнен рабочий каркас]**

> **A7 (High)**: В v3.3 содержал только комментарии вместо JSX. Добавлен полный рабочий каркас: кнопки сохранения/сброса, раскрывающийся список пресетов, создание/удаление пресетов.

```typescript
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

  useEffect(() => {
    fetchPresets().then((res) => setPresets(res.presets)).catch(() => {});
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await saveConfig(config);
    } finally {
      setSaving(false);
    }
  }, [config]);

  const handleReset = useCallback(async () => {
    const result = await fetchDefaults();
    onConfigReset(result.config);
  }, [onConfigReset]);

  const handleCreatePreset = useCallback(async () => {
    if (!presetName.trim()) return;
    await createPreset(presetName, config);
    setPresetName("");
    const res = await fetchPresets();
    setPresets(res.presets);
  }, [presetName, config]);

  const handleDeletePreset = useCallback(async (name: string) => {
    await deletePreset(name);
    setPresets(prev => prev.filter(p => p.name !== name));
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <button onClick={handleSave} disabled={saving}
          className="flex-1 px-3 py-2 bg-accent-blue text-white rounded text-sm hover:opacity-90 disabled:opacity-50">
          {saving ? "Сохранение..." : "Сохранить config.yaml"}
        </button>
        <button onClick={handleReset}
          className="px-3 py-2 bg-bg-card text-text-secondary rounded text-sm hover:bg-bg-hover">
          Сброс
        </button>
      </div>

      <button onClick={() => setShowPresets(!showPresets)}
        className="w-full text-left text-sm text-text-muted hover:text-text-secondary">
        Пресеты ({presets.length}) ▾
      </button>

      {showPresets && (
        <div className="space-y-2">
          {presets.map((p) => (
            <div key={p.name} className="flex items-center gap-2">
              <button onClick={() => onConfigChange(p.config)}
                className="flex-1 text-left px-2 py-1 text-sm bg-bg-card rounded hover:bg-bg-hover">
                {p.name}
              </button>
              <button onClick={() => handleDeletePreset(p.name)}
                className="text-accent-red text-xs hover:underline">✕</button>
            </div>
          ))}
          <div className="flex gap-1">
            <input value={presetName} onChange={(e) => setPresetName(e.target.value)}
              placeholder="Имя пресета" className="flex-1 bg-bg-input text-sm px-2 py-1 rounded" />
            <button onClick={handleCreatePreset}
              className="px-2 py-1 text-sm bg-bg-card rounded hover:bg-bg-hover">+</button>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Структура каркаса (A7)**:
- **Сохранить config.yaml** — `saveConfig(config)` с индикатором загрузки
- **Сброс** — `fetchDefaults()` → `onConfigReset(result.config)`
- **Пресеты** — раскрывающийся список с `fetchPresets()`, клик применяет конфиг, `✕` удаляет
- **Создать пресет** — инпут имени + кнопка `+`
- Агент может заменить на shadcn `<Dialog>` для создания пресета

### export-buttons.tsx

```typescript
/** Экспорт TIFF/PNG по fileId */
import { useState } from "react";
import { fetchExport } from "../lib/api";

interface Props {
  fileId: string | null;
  machineType: "laser" | "impact";
  config: Record<string, any>;
}

export function ExportButtons({ fileId, machineType, config }: Props) {
  const [exporting, setExporting] = useState(false);

  const handleExport = async (format: "tiff" | "png") => {
    if (!fileId) return;
    setExporting(true);
    try {
      const blob = await fetchExport(fileId, machineType, format, config);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `retouch_result.${format === "tiff" ? "tif" : "png"}`;
      a.click();
      URL.revokeObjectURL(url);  // Освободить Object URL
    } catch (e: any) {
      alert(`Ошибка экспорта: ${e.message}`);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex gap-2">
      <button
        onClick={() => handleExport("tiff")}
        disabled={!fileId || exporting}
        className="px-4 py-2 bg-bg-card text-text-primary rounded hover:bg-bg-hover disabled:opacity-50"
      >
        TIFF
      </button>
      <button
        onClick={() => handleExport("png")}
        disabled={!fileId || exporting}
        className="px-4 py-2 bg-bg-card text-text-primary rounded hover:bg-bg-hover disabled:opacity-50"
      >
        PNG
      </button>
    </div>
  );
}
```

---

## Задача 6a: hooks/use-config.ts **[A6 — полная реализация]**

> **A6 (High)**: В v3.3 хук `useConfig` использовался в App.tsx, но его реализация отсутствовала. Добавлена полная реализация: загрузка конфига с бэкенда, updateConfig, resetConfig, warnings.

```typescript
import { useState, useEffect, useCallback } from "react";
import { fetchConfig, fetchDefaults, type ConfigResult } from "../lib/api";

interface UseConfigReturn {
  config: Record<string, any>;
  warnings: string[];
  updateConfig: (newConfig: Record<string, any>) => void;
  resetConfig: (defaults?: Record<string, any>) => void;
}

export function useConfig(): UseConfigReturn {
  const [config, setConfig] = useState<Record<string, any>>({});
  const [warnings, setWarnings] = useState<string[]>([]);

  useEffect(() => {
    fetchConfig().then((result: ConfigResult) => {
      setConfig(result.config);
      setWarnings(result.warnings);
    }).catch(() => {
      // Backend unavailable — use empty config
    });
  }, []);

  const updateConfig = useCallback((newConfig: Record<string, any>) => {
    setConfig(newConfig);
  }, []);

  const resetConfig = useCallback(async (defaults?: Record<string, any>) => {
    if (defaults) {
      setConfig(defaults);
    } else {
      const result = await fetchDefaults();
      setConfig(result.config);
      setWarnings(result.warnings);
    }
  }, []);

  return { config, warnings, updateConfig, resetConfig };
}
```

**Поведение хука**:
- **Загрузка при монтировании**: `fetchConfig()` → заполнить `config` и `warnings`
- **updateConfig(newConfig)**: заменить весь конфиг (вызывается при изменении слайдера, применении пресета)
- **resetConfig(defaults?)**: если переданы defaults — использовать их; иначе — `fetchDefaults()` с бэкенда
- **Backend unavailable**: `catch()` — пустой конфиг, UI показывает значения по умолчанию из CONFIG_SCHEMA
- `warnings` — массив строк от валидации бэкенда (out-of-range и т.д.)

---

## Задача 7: App.tsx — главный layout

Главный компонент — собирает все компоненты в единый layout.

```typescript
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
  // Состояние
  const [fileId, setFileId] = useState<string | null>(null);
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);
  const [machineType, setMachineType] = useState<"laser" | "impact">("laser");
  const [selectedStep, setSelectedStep] = useState("final");
  const [backendDown, setBackendDown] = useState(false);

  // Хуки
  const { result: previewResult, loading, error: previewError, requestPreview } = usePreview(300);
  const { config, updateConfig, resetConfig, warnings: configWarnings } = useConfig();

  // Обработчики
  const handleImageUploaded = useCallback((newFileId: string, previewUrl: string) => {
    setFileId(newFileId);
    setOriginalUrl(previewUrl);
    // Автоматический предпросмотр после загрузки
    requestPreview(newFileId, machineType, config);
  }, [machineType, config, requestPreview]);

  const handleMachineChange = useCallback((type: "laser" | "impact") => {
    setMachineType(type);
    if (fileId) requestPreview(fileId, type, config);
  }, [fileId, config, requestPreview]);

  const handleConfigChange = useCallback((newConfig: Record<string, any>) => {
    updateConfig(newConfig);
    if (fileId) requestPreview(fileId, machineType, newConfig);
  }, [fileId, machineType, updateConfig, requestPreview]);

  // Layout: сайдбар слева (параметры) + основная область (изображение) справа
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary flex flex-col">
      {/* Хедер */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-border">
        <h1 className="text-xl font-heading font-semibold">Granite Retouch</h1>
        <div className="flex gap-4 items-center">
          <MachineSwitch value={machineType} onChange={handleMachineChange} />
          <ExportButtons fileId={fileId} machineType={machineType} config={config} />
        </div>
      </header>

      {/* Баннер: backend недоступен */}
      {backendDown && (
        <div className="bg-accent-orange/20 text-accent-orange px-6 py-2 text-sm">
          Backend не запущен. Запустите: <code>make ui-backend</code>
        </div>
      )}

      {/* Основной контент */}
      <div className="flex flex-1 overflow-hidden">
        {/* Сайдбар: параметры */}
        <aside className="w-80 border-r border-border overflow-y-auto p-4 space-y-4">
          {!fileId ? (
            <ImageUpload onImageUploaded={handleImageUploaded} />
          ) : (
            <>
              <ParamsPanel
                machineType={machineType}
                config={config}
                onConfigChange={handleConfigChange}
              />
              <ConfigActions
                config={config}
                onConfigReset={resetConfig}
                onConfigChange={handleConfigChange}
              />
              <DiagnosticsPanel
                diagnostics={previewResult?.diagnostics ?? null}
                warnings={previewResult?.warnings ?? []}
              />
              {/* Кнопка смены изображения */}
              <button
                onClick={() => { setFileId(null); setOriginalUrl(null); }}
                className="text-sm text-text-muted hover:text-text-secondary"
              >
                Сменить изображение
              </button>
            </>
          )}
        </aside>

        {/* Основная область: изображение */}
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
              {loading ? "Обработка..." : "Загрузите изображение для предпросмотра"}
            </div>
          )}
          {previewError && (
            <p className="text-accent-red text-sm">{previewError}</p>
          )}
        </main>
      </div>
    </div>
  );
}
```

**Структура layout**:
- Хедер: название + MachineSwitch + ExportButtons
- Сайдбар (320px): параметры, конфиг, диагностика
- Основная область: StepSelector + BeforeAfter
- При отсутствии fileId — ImageUpload вместо параметров

---

## Порядок выполнения

1. Инициализация проекта (Vite + shadcn)
2. index.css с дизайн-токенами
3. config-schema.ts
4. lib/api.ts (с uploadImage → file_id)
5. hooks/use-preview.ts, hooks/use-config.ts ← **[A6: добавлена полная реализация]**
6. image-upload.tsx ← **[A17: useRef + onClick]**
7. machine-switch.tsx
8. params-panel.tsx ← **[A7: рабочий каркас вместо заглушки]**
9. before-after.tsx + step-selector.tsx
10. diagnostics-panel.tsx
11. config-actions.tsx ← **[A7: рабочий каркас вместо заглушки]**
12. export-buttons.tsx
13. App.tsx — сборка layout
14. Проверка с мок-API (можно до готовности backend)

---

## Чеклист приёмки

- [ ] `npm run dev` запускается, RAM ≤ 300 МБ
- [ ] Drag & drop загружает PNG → получен fileId
- [ ] **Клик по зоне загрузки** открывает файловый диалог (A17)
- [ ] До/После отображается side-by-side
- [ ] Переключение шагов (chromakey, glow, levels, final) обновляет «После»
- [ ] **Слайдеры параметров работают**, значения обновляются (A7)
- [ ] Переключение laser/impact меняет набор параметров
- [ ] Диагностика отображает face brightness, glow, black ratio
- [ ] **Сохранение конфига через UI** — кнопка вызывает API (A7)
- [ ] **Сброс к дефолтам** — загружает /config/defaults (A7)
- [ ] **Пресеты загружаются** — раскрывающийся список с CRUD (A7)
- [ ] **useConfig() загружает конфиг при монтировании** (A6)
- [ ] **useConfig().resetConfig()** — с defaults или без (A6)
- [ ] Экспорт скачивает файл
- [ ] Тёмная тема, чистый фон #1a1a1a
- [ ] Нет glassmorphism, нет backdrop-filter
- [ ] Обновить BACKLOG.md — отметить завершённые задачи (A8)
