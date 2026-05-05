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
            │   ├── image-upload.tsx      # Drag & drop загрузка
            │   ├── before-after.tsx      # До/После (side-by-side или табы)
            │   ├── step-selector.tsx     # Переключатель промежуточных шагов
            │   ├── params-panel.tsx      # Слайдеры параметров
            │   ├── machine-switch.tsx    # Переключатель laser/impact
            │   ├── diagnostics-panel.tsx # Диагностика обработки
            │   ├── config-actions.tsx    # Сохранить / Сброс / Пресеты
            │   └── export-buttons.tsx    # Экспорт TIFF/PNG
            ├── lib/
            │   ├── api.ts               # Фетчеры к FastAPI
            │   ├── config-schema.ts     # Типы + диапазоны параметров
            │   └── utils.ts             # cn() и утилиты
            └── hooks/
                ├── use-preview.ts        # Предпросмотр с debounce
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

Прокси `/api` → FastAPI. В продакшене (если будет) — nginx reverse proxy. При разработке — одна команда `npm run dev`, запросы к `/api/*` проксируются автоматически.

---

## Задача 2: index.css — дизайн-токены

```css
@import "tailwindcss";
@import "@fontsource/outfit/400-700.css";
@import "@fontsource/inter/400-500.css";

:root {
  /* Фоны */
  --bg-primary: #1a1a1a;
  --surface-bg: #242424;
  --surface-border: #333333;

  /* Цвета статусов (минеральная палитра) */
  --color-primary: #7C8CF8;     /* Лабрадорит */
  --color-success: #34D399;     /* Малахит */
  --color-warning: #FBBF24;     /* Янтарь */
  --color-destructive: #F43F5E; /* Гранат */
  --color-info: #60A5FA;        /* Сапфир */

  /* Текст */
  --heading-color: #E4E5E9;
  --text-color: #D0D0D0;
  --text-muted: #888888;

  /* Радиусы */
  --radius-lg: 16px;
  --radius-md: 8px;

  /* Тени — минимальные, без glassmorphism */
  --shadow-card: 0 2px 8px rgba(0,0,0,0.3);

  /* Переходы */
  --transition-micro: 0.15s ease;
  --transition-normal: 0.3s ease;
}

body {
  font-family: 'Inter', system-ui, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-color);
  margin: 0;
}

h1, h2, h3, h4, h5, h6 {
  font-family: 'Outfit', system-ui, sans-serif;
  color: var(--heading-color);
  font-weight: 600;
}
```

**Нет glassmorphism, нет backdrop-filter, нет прозрачностей.** Чистый непрозрачный тёмный фон — инструмент для оценки яркости, визуальный шум недопустим.

---

## Задача 3: config-schema.ts — типы и диапазоны

```typescript
/** Определение одного параметра */
export interface ParamDef {
  key: string;                    // Путь в конфиге: "processing.laser.brightness"
  label: string;                  // Метка в UI
  min: number;
  max: number;
  step: number;
  defaultValue: number | [number, number];
  unit?: string;                  // "px", "%"
  group: "processing" | "laser" | "impact" | "vignette";
  description: string;
}

export const PARAM_DEFS: ParamDef[] = [
  // === Processing (общие) ===
  {
    key: "processing.blue_threshold",
    label: "Порог хромакея",
    min: 10, max: 80, step: 1, defaultValue: 30,
    group: "processing",
    description: "Чувствительность определения синего фона",
  },
  {
    key: "processing.fringe_radius",
    label: "Устранение ореола",
    min: 0, max: 10, step: 1, defaultValue: 3, unit: "px",
    group: "processing",
    description: "Радиус fringe removal вокруг контура",
  },

  // === Laser ===
  {
    key: "processing.laser.brightness",
    label: "Яркость",
    min: 0.50, max: 1.50, step: 0.01, defaultValue: 1.18,
    group: "laser",
    description: "Множитель яркости",
  },
  {
    key: "processing.laser.glow_size_min",
    label: "Glow мин.",
    min: 5, max: 100, step: 1, defaultValue: 40, unit: "px",
    group: "laser",
    description: "Минимальный размер Inner Glow",
  },
  {
    key: "processing.laser.glow_size_max",
    label: "Glow макс.",
    min: 5, max: 100, step: 1, defaultValue: 80, unit: "px",
    group: "laser",
    description: "Максимальный размер Inner Glow",
  },
  {
    key: "processing.laser.glow_opacity_min",
    label: "Glow opacity мин.",
    min: 10, max: 100, step: 1, defaultValue: 30, unit: "%",
    group: "laser",
    description: "Минимальная непрозрачность Inner Glow",
  },
  {
    key: "processing.laser.glow_opacity_max",
    label: "Glow opacity макс.",
    min: 10, max: 100, step: 1, defaultValue: 40, unit: "%",
    group: "laser",
    description: "Максимальная непрозрачность Inner Glow",
  },
  {
    key: "processing.laser.face_brightness_target",
    label: "Целевая яркость лица",
    min: 50, max: 255, step: 1, defaultValue: [230, 245],
    group: "laser",
    description: "Диапазон целевой яркости [мин, макс]",
  },

  // === Impact ===
  {
    key: "processing.impact.brightness",
    label: "Яркость",
    min: 0.50, max: 1.50, step: 0.01, defaultValue: 1.00,
    group: "impact",
    description: "Множитель яркости",
  },
  {
    key: "processing.impact.glow_size_min",
    label: "Glow мин.",
    min: 5, max: 100, step: 1, defaultValue: 10, unit: "px",
    group: "impact",
    description: "Минимальный размер Inner Glow",
  },
  {
    key: "processing.impact.glow_size_max",
    label: "Glow макс.",
    min: 5, max: 100, step: 1, defaultValue: 25, unit: "px",
    group: "impact",
    description: "Максимальный размер Inner Glow",
  },
  {
    key: "processing.impact.glow_opacity_min",
    label: "Glow opacity мин.",
    min: 10, max: 100, step: 1, defaultValue: 60, unit: "%",
    group: "impact",
    description: "Минимальная непрозрачность Inner Glow",
  },
  {
    key: "processing.impact.glow_opacity_max",
    label: "Glow opacity макс.",
    min: 10, max: 100, step: 1, defaultValue: 80, unit: "%",
    group: "impact",
    description: "Максимальная непрозрачность Inner Glow",
  },
  {
    key: "processing.impact.face_brightness_target",
    label: "Целевая яркость лица",
    min: 50, max: 255, step: 1, defaultValue: [185, 210],
    group: "impact",
    description: "Диапазон целевой яркости [мин, макс]",
  },

  // === Vignette ===
  {
    key: "vignette.vertical_offset",
    label: "Отступ арки",
    min: 0.0, max: 0.3, step: 0.01, defaultValue: 0.10,
    group: "vignette",
    description: "Отступ нижнего края арки",
  },
  {
    key: "vignette.vertical_diameter",
    label: "Высота арки",
    min: 0.2, max: 0.8, step: 0.01, defaultValue: 0.50,
    group: "vignette",
    description: "Высота эллипса виньетки",
  },
  {
    key: "vignette.blur_radius",
    label: "Размытие края",
    min: 10, max: 120, step: 1, defaultValue: 60, unit: "px",
    group: "vignette",
    description: "Размытие перехода виньетки",
  },
  {
    key: "vignette.headroom",
    label: "Запас над головой",
    min: 0.2, max: 1.0, step: 0.01, defaultValue: 0.60,
    group: "vignette",
    description: "Расстояние от макушки до верхнего края арки",
  },
  {
    key: "vignette.horizontal_oversize",
    label: "Расширение по бокам",
    min: 0.0, max: 0.5, step: 0.01, defaultValue: 0.20,
    group: "vignette",
    description: "Насколько эллипс шире изображения",
  },
];

/** Получить параметры для текущего machine_type */
export function getParamsForMachine(machine: "laser" | "impact"): ParamDef[] {
  return PARAM_DEFS.filter(p =>
    p.group === "processing" || p.group === machine || p.group === "vignette"
  );
}
```

---

## Задача 4: lib/api.ts — фетчеры к backend

```typescript
const API_BASE = "/api";

export interface PreviewResult {
  images: Record<string, string>;  // step → base64 data URI
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

/** Предпросмотр обработки */
export async function fetchPreview(
  file: File,
  machineType: "laser" | "impact",
  configOverride?: Record<string, any>,
): Promise<PreviewResult> {
  const formData = new FormData();
  formData.append("file", file);
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

/** Экспорт результата */
export async function fetchExport(
  file: File,
  machineType: "laser" | "impact",
  format: "tiff" | "png",
  configOverride?: Record<string, any>,
): Promise<Blob> {
  const formData = new FormData();
  formData.append("file", file);
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

---

## Задача 5: hooks/use-preview.ts

```typescript
import { useState, useCallback, useRef, useEffect } from "react";
import { fetchPreview, type PreviewResult } from "../lib/api";

interface UsePreviewReturn {
  result: PreviewResult | null;
  loading: boolean;
  error: string | null;
  requestPreview: (file: File, machineType: "laser" | "impact", config?: Record<string, any>) => void;
}

export function usePreview(debounceMs = 300): UsePreviewReturn {
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const requestPreview = useCallback(
    (file: File, machineType: "laser" | "impact", config?: Record<string, any>) => {
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
          const data = await fetchPreview(file, machineType, config);
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

  // Cleanup
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (abortRef.current) abortRef.current.abort();
    };
  }, []);

  return { result, loading, error, requestPreview };
}
```

**Ключевые решения:**
- **Debounce 300ms** — не отправлять запрос на каждое движение слайдера
- **AbortController** — отменить предыдущий запрос если пришёл новый
- **Нет кэша на стороне клиента** — backend может кэшировать, но frontend всегда запрашивает свежие данные

---

## Задача 6: Компоненты

### image-upload.tsx

```
Drag & drop зона + клик → файловый диалог
Валидация: PNG/JPEG, < 20 МБ
После загрузки → callback onImageSelected(file)
Состояние: пустое / загружено (превью исходника)
```

### before-after.tsx

```
Отображение «До / После»:
- Side-by-side (два изображения рядом) — по умолчанию
- Переключение через табы если ширина < 768px

Пропсы:
  beforeSrc: string (base64 data URI исходника)
  afterSrc: string (base64 data URI результата)
  activeStep: string (какой промежуточный шаг показан в «После»)

«До» — всегда оригинал
«После» — зависит от activeStep:
  "final" → img_final
  "chromakey" → img_chromakey
  "glow" → img_glow
  "leveled" → img_leveled
  "face_corrected" → img_face_corrected
```

### step-selector.tsx

```
Горизонтальный ряд кнопок-табов:
[Оригинал] [Хромакей] [Glow] [Levels] [Лицо] [Результат]

Активный таб подсвечен --color-primary
При клике → callback onStepChange(step)
```

### params-panel.tsx

```
Группировка слайдеров:
── Общие ──
  Порог хромакея    [====30====]
  Устранение ореола [==3===] px

── Laser (или Impact) ──
  Яркость           [===1.18===]
  Glow мин.         [===40===] px
  Glow макс.        [===80===] px
  ...

── Виньетка ──
  Отступ арки       [==0.10==]
  Высота арки       [==0.50==]
  ...

Каждый параметр: shadcn Slider + числовой Input справа
При изменении → callback onParamChange(key, value)
Красная подсветка при выходе за диапазон
```

### machine-switch.tsx

```
Два toggle-кнопки: [Laser] [Impact]
Активная — --color-primary, неактивная — серая
При переключении → callback onMachineChange(type)
Параметры в params-panel обновляются
```

### diagnostics-panel.tsx

```
Карточка с метриками:
  Face brightness: 178 → 218  (factor: 1.12)
    ↑ зелёный если в диапазоне, красный если нет
  Glow: 52px / 35%
    ↑ текст «preview mid, range 40–80»
  Black background: 42%
    ↑ зелёный если ≥ 25%, красный если нет
  Размер: 2048 × 2048

Все значения из diagnostics ответа API
```

### config-actions.tsx

```
Ряд кнопок:
[Сохранить] → PUT /api/config
[Сброс] → применить DEFAULTS из GET /api/config/defaults
[Пресеты ▾] → dropdown с пресетами из GET /api/presets
  → при выборе — загрузить конфиг пресета в слайдеры

Предупреждения валидации — красные badge
```

### export-buttons.tsx

```
[Экспорт TIFF]  [Экспорт PNG]
При клике → POST /api/process/export → скачать файл
Кнопки неактивны пока нет загруженного изображения
```

---

## Задача 7: App.tsx — главный layout

```
┌─────────────────────────────────────────────────────────┐
│  granite-retouch                        [Laser] [Impact] │
├───────────────────────────────┬─────────────────────────┤
│                               │                         │
│    ДО           ПОСЛЕ         │   ПАРАМЕТРЫ              │
│                               │                         │
│  ┌──────────┐  ┌──────────┐  │   ── Общие ──           │
│  │          │  │          │  │   ...                    │
│  │ исходник │  │ результ  │  │                         │
│  │          │  │          │  │   ── Laser ──            │
│  └──────────┘  └──────────┘  │   ...                    │
│                               │                         │
│  [Ориг][Хром][Glow][Lev][Fin]│   ── Виньетка ──        │
│                               │   ...                    │
│  ┌────────────────────────┐  │                         │
│  │  ДИАГНОСТИКА           │  │  [Сохранить] [Сброс]    │
│  │  Face: 178 → 218       │  │  [Пресеты ▾]            │
│  │  Glow: 52px / 35%      │  │                         │
│  │  Black bg: 42%          │  │                         │
│  └────────────────────────┘  │                         │
│                               │                         │
├───────────────────────────────┴─────────────────────────┤
│  [Экспорт TIFF]  [Экспорт PNG]                          │
└─────────────────────────────────────────────────────────┘
```

**Responsive**:
- Desktop (≥1024px): side-by-side как на схеме
- Tablet (768–1023px): параметры под preview, вертикальная раскладка
- Mobile (<768px): минимальная адаптация, не приоритет

---

## Порядок выполнения

1. Инициализация проекта (Vite + shadcn)
2. index.css с дизайн-токенами
3. config-schema.ts
4. lib/api.ts
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
- [ ] Drag & drop загружает PNG
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
