# Фаза 2: React + Vite Frontend

**Предыдущий этап**: [Фаза 1](dev-plan-phase1-backend.md) (можно параллелить с мок-API)
**Следующий этап**: [Фаза 3](dev-plan-phase3-integration.md)
**Время**: 8–12 часов
**Цель**: Интерактивный UI для настройки параметров ретуши с предпросмотром до/после.

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
└── retouch-ui/
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
            │   ├── image-upload.tsx      # Drag & drop загрузка → file_id
            │   ├── before-after.tsx      # До/После (side-by-side или табы)
            │   ├── step-selector.tsx     # Переключатель промежуточных шагов
            │   ├── params-panel.tsx      # Слайдеры параметров
            │   ├── machine-switch.tsx    # Переключатель laser/impact
            │   ├── diagnostics-panel.tsx # Диагностика обработки
            │   ├── config-actions.tsx    # Сохранить / Сброс / Пресеты
            │   └── export-buttons.tsx    # Экспорт TIFF/PNG
            ├── lib/
            │   ├── api.ts               # Фетчеры: uploadImage → file_id, fetchPreview(fileId, ...)
            │   ├── config-schema.ts     # Типы + диапазоны параметров
            │   └── utils.ts             # cn() и утилиты
            └── hooks/
                ├── use-preview.ts        # Предпросмотр с debounce (по file_id)
                └── use-config.ts         # Управление конфигом
```

---

## Задача 1: Инициализация проекта

```bash
cd retouch-ui
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

Без изменений — см. v3.0. Плоский тёмный фон, нет glassmorphism, нет backdrop-filter.

---

## Задача 3: config-schema.ts

Без изменений — см. v3.0.

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
          const data = await fetchPreview(fileId, machineType, config);
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

Без изменений — см. v3.0. Кратко:

- **image-upload.tsx**: Загрузка → `uploadImage(file)` → получение `fileId` → callback `onImageUploaded(fileId, previewUrl)`
- **before-after.tsx**: Side-by-side до/после, табы для шагов
- **step-selector.tsx**: [Оригинал] [Хромакей] [Glow] [Levels] [Лицо] [Результат]
- **params-panel.tsx**: Группировка слайдеров: Общие → Laser/Impact → Виньетка
- **machine-switch.tsx**: [Laser] [Impact]
- **diagnostics-panel.tsx**: Face brightness, glow, black ratio
- **config-actions.tsx**: Сохранить / Сброс / Пресеты
- **export-buttons.tsx**: Экспорт TIFF/PNG по fileId

---

## Задача 7: App.tsx — главный layout

Без изменений — см. v3.0.

---

## Порядок выполнения

1. Инициализация проекта (Vite + shadcn)
2. index.css с дизайн-токенами
3. config-schema.ts
4. lib/api.ts (с uploadImage → file_id)
5. hooks/use-preview.ts, hooks/use-config.ts
6. image-upload.tsx
7. machine-switch.tsx
8. params-panel.tsx
9. before-after.tsx + step-selector.tsx
10. diagnostics-panel.tsx
11. config-actions.tsx
12. export-buttons.tsx
13. App.tsx — сборка layout
14. Проверка с мок-API (можно до готовности backend)

---

## Чеклист приёмки

- [ ] `npm run dev` запускается, RAM ≤ 300 МБ
- [ ] Drag & drop загружает PNG → получен fileId
- [ ] До/После отображается side-by-side
- [ ] Переключение шагов (chromakey, glow, levels, final) обновляет «После»
- [ ] Слайдеры параметров работают, значения обновляются
- [ ] Переключение laser/impact меняет набор параметров
- [ ] Диагностика отображает face brightness, glow, black ratio
- [ ] Сохранение конфига через UI
- [ ] Сброс к дефолтам
- [ ] Пресеты загружаются
- [ ] Экспорт скачивает файл
- [ ] Тёмная тема, чистый фон #1a1a1a
- [ ] Нет glassmorphism, нет backdrop-filter
