# Development Guide — granite-retouch Frontend

## Архитектура компонентов

### Portrait Split Layout

```
App.tsx
├── header: Logo + MachineSelector + MaterialSelector(compact) + overlay toggles + ExportButtons
├── step-bar: StepSelector + dither + «Сменить фото»
├── left-col (360px)
│   ├── [no file] ImageUpload(fullHeight)
│   ├── [with file] BeforeImage
│   ├── ParamsPanel (collapsible accordions)
│   │   ├── ParamGroup (Основные)
│   │   ├── ParamGroup (Glow)
│   │   ├── ParamGroup (Лицо)
│   │   ├── ParamGroup (Тени) — impact only
│   │   ├── ParamGroup (Виньетка)
│   │   └── ParamGroup (Продвинутые) — Advanced toggle
│   ├── toggle-бар (collapsed ParamsPanel)
│   └── footer: ConfigActions + DiagnosticsPanel(compact)
└── canvas (flex:1, bg-canvas #111)
    ├── AfterImage + overlays (vignette, face oval)
    ├── loading/error/empty states
    ├── return-arrow (when leftColHidden)
    └── compare button / compare mode (BeforeImage + AfterImage side by side)
```

### Ключевые компоненты

| Компонент | Файл | Назначение |
|-----------|------|------------|
| `BeforeImage` | `before-image.tsx` | Оригинал с object-contain + бейдж размеров |
| `AfterImage` | `after-image.tsx` | Результат + оверлеи (useRenderMetrics) |
| `BeforeAfter` | `before-after.tsx` | Тонкая обёртка BeforeImage + AfterImage |
| `ParamGroup` | `param-group.tsx` | Аккордеон: chevron, badge, слайдеры/тогглы |
| `ParamsPanel` | `params-panel.tsx` | Фильтрует секции, рендерит ParamGroup |
| `DiagnosticsPanel` | `diagnostics-panel.tsx` | Метрики: face, glow, black ratio; compact mode |
| `ImageUpload` | `image-upload.tsx` | Drag & drop / click upload; fullHeight prop |

### Хуки

| Хук | Файл | Назначение |
|-----|------|------------|
| `useRenderMetrics` | `hooks/use-render-metrics.ts` | Возвращает `renderedWidth/Height`, `offsetX/Y`, `onImgLoad` для позиционирования оверлеев поверх `object-contain`. Использует `ResizeObserver` |

### Состояния App.tsx

| State | Тип | Управление |
|-------|-----|------------|
| `paramsCollapsed` | boolean | Клик по toggle-bar + `P`/`З` |
| `leftColHidden` | boolean | `[`/`Х` + canvas return-arrow |
| `compareMode` | boolean | Кнопка «Сравнить» + `Escape` |

## Дизайн-система

### Токены CSS (`@theme` в `index.css`)

```css
@theme {
  /* Canvas */
  --color-bg-canvas: #111111;
  --width-left-col: 360px;

  /* Overlays */
  --color-overlay-vignette: rgba(255, 255, 255, 0.15);
  --color-overlay-handle: rgba(0, 122, 255, 0.8);
  --color-overlay-handle-active: rgba(0, 122, 255, 1);
  --color-overlay-guide: rgba(255, 255, 255, 0.4);
  --color-overlay-guide-active: rgba(255, 255, 255, 0.8);
  --color-overlay-mask-fill: rgba(30, 30, 30, 0.25);
  --color-overlay-mask-stroke: rgba(255, 255, 255, 0.5);
  --color-overlay-pin-active: #ff6b35;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 2px 6px rgba(0,0,0,0.35);
  --shadow-lg: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-xl: 0 8px 24px rgba(0,0,0,0.45);

  /* Durations */
  --duration-200: 200ms;
}
```

### Типографика

| Класс | Применение |
|-------|------------|
| `font-heading` | Inter 600 — заголовки секций |
| `font-mono` | JetBrains Mono — числовые значения (слайдеры, бейджи, диагностика) |
| `text-xs font-mono` | Бейджи, compact diagnostics |
| `text-sm font-heading font-semibold` | Заголовки «До», «После», «Параметры» |

### Цветовая палитра

| Токен | Значение | Применение |
|-------|----------|------------|
| `--color-bg-primary` | bg-primary | Фон страницы |
| `--color-bg-secondary` | bg-secondary | Фон контейнеров изображений |
| `--color-bg-card` | bg-card | Фон карточек (аккордеоны, footer) |
| `--color-bg-hover` | bg-hover | Ховер интерактивных элементов |
| `--color-bg-input` | bg-input | Фон инпутов/кнопок toggle |
| `--color-text-primary` | text-primary | Основной текст |
| `--color-text-secondary` | text-secondary | Вторичный текст |
| `--color-text-muted` | text-muted | Мутированный текст (#888 для non-text) |
| `--color-accent-blue` | accent-blue | Акцент (выделение, primary) |
| `--color-accent-orange` | accent-orange | Акцент (предупреждения) |
| `--color-accent-red` | accent-red | Ошибки |
| `--color-accent-green` | accent-green | Успех |
| `--color-border` | border | Границы |

## Конфигурация параметров

### PARAM_SECTIONS

Определён в `config-schema.ts:220`. Массив секций-аккордеонов:

```typescript
interface ParamSection {
  key: string;           // уникальный ключ
  label: string;         // отображаемое название
  icon: string;          // Remix icon class
  params: string[];      // ключи параметров
  configPath?: string;   // альтернативный путь в ConfigTree
  machineType?: string;  // фильтр по станку (например "impact")
  advancedOnly?: boolean; // показывать только при Advanced toggle
}
```

Секции: `main`, `glow`, `face`, `shadow` (impact), `vignette`, `advanced`.

Схема параметров хранится в `CONFIG_SCHEMA` (также `config-schema.ts`) — дерево из `ParamRange` (слайдеры) и `ParamToggle` (переключатели).
