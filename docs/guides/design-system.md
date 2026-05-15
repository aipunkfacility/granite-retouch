## Дизайн-система Granite

### 1. Общие принципы

В основе дизайн-системы лежат три ключевых принципа: **Эффективность**, **Прозрачность** и **Надёжность**. Интерфейс не должен отвлекать пользователя; он должен служить инструментом для быстрого принятия решений.

### 2. Цветовая палитра

#### 2.1 Акцентные цвета (общие для CRM и Retouch)

| Категория | Цвет | HEX | Применение |
| :--- | :--- | :--- | :--- |
| **Primary** | Labradorite | light: `#5B6ABF`, dark: `#7C8CF8` | Кнопки, активные состояния, ссылки |
| **Success** | Emerald | `#10B981` | Положительные статусы, завершённые задачи |
| **Warning** | Amber | `#F59E0B` | Внимание, ожидающие действия, пауза |
| **Destructive** | Rose | `#E11D48` | Ошибки, удаление, критические алерты |

#### 2.2 Granite Retouch (тёмная тема)

| Категория | HEX | Переменная |
| :--- | :--- | :--- |
| **Background** | `#1a1a1a` | `--color-bg-primary` |
| **Secondary** | `#222222` | `--color-bg-secondary` |
| **Surface** | `#2a2a2a` | `--color-bg-card` |
| **Input** | `#333333` | `--color-bg-input` |
| **Hover** | `#3a3a3a` | `--color-bg-hover` |
| **Text Primary** | `#f0f0f0` | `--color-text-primary` |
| **Text Secondary** | `#a0a0a0` | `--color-text-secondary` |
| **Text Muted** | `#888888` | `--color-text-muted` |
| **Border** | `#3a3a3a` | `--color-border` |
| **Focus** | `#7C8CF8` | `--color-border-focus` |

#### 2.3 Granite CRM (светлая тема)

| Категория | HEX | Применение |
| :--- | :--- | :--- |
| **Background** | `#F8FAFC` | Основной фон CRM |
| **Surface** | `#FFFFFF` | Карточки, таблицы, панели |
| **Text Primary** | `#0F172A` | Ink Blue — заголовки, основной текст |
| **Text Muted** | `#64748B` | Slate Gray — подписи, второстепенная информация |

### 3. Типографика

- **Заголовки:** Outfit, Semibold (600)
- **Основной текст:** Inter, Regular (400), 14px
- **Моноширинный:** JetBrains Mono, 13px (для ID/кода, числовых значений слайдеров)

### 4. Иконки

**Remix Icon** (`ri-*`) — основная библиотека иконок для Granite Retouch и CRM. Контурные, размер 16-20px.

### 5. Запрещённые паттерны

Классы `*-50`, `*-100`, `*-200` из стандартной палитры Tailwind запрещены для тёмной темы Granite Retouch. Эти классы предназначены для светлых фонов и на тёмной теме выглядят неестественно. Использовать только `--color-accent-*/N` (с opacity) и `--color-bg-*`.

**Запрещено:**
```tsx
// Светлая палитра — НЕ использовать в тёмной теме
<div className="bg-yellow-50 text-yellow-700 border-yellow-200" />
<div className="bg-red-50 text-red-700 border-red-200" />
<div className="bg-green-50 text-green-700 border-green-200" />
```

**Правильно:**
```tsx
// Тёмная палитра с accent-переменными и opacity
<div className="bg-accent-orange/10 text-accent-orange border-accent-orange/30" />
<div className="bg-accent-red/10 text-accent-red border-accent-red/30" />
<div className="bg-accent-green/10 text-accent-green border-accent-green/30" />
```

### 6. MACHINE_THEME

Единый источник тем станков — `lib/machine-theme.ts`. Экспортирует `MACHINE_THEME: Record<MachineType, MachineTheme>` с полями `bg`, `border`, `dot`, `icon`, `label`.

| MachineType | bg | border | dot | icon | label |
|:---|:---|:---|:---|:---|:---|
| `impact` | `bg-accent-orange/10` | `border-accent-orange/30` | `bg-accent-orange` | `ri-contrast-2-line` | Ударный |
| `laser_standard` | `bg-accent-green/10` | `border-accent-green/30` | `bg-accent-green` | `ri-flashlight-line` | CO2 40W |
| `laser_80w` | `bg-accent-red/10` | `border-accent-red/30` | `bg-accent-red` | `ri-flashlight-fill` | Диод 80W |

Устаревший `MACHINE_COLORS` удалён — использовать `MACHINE_THEME`.

### 7. Компоненты

#### 7.1 Granite Retouch

- **Sidebar (320px)** — параметры, диагностика, настройки станка
- **Image Preview** — before/after компаратор
- **Slider** — кастомный range input с заполнением трека и иконкой сброса (см. 7.2)
- **Step Selector** — кнопки шагов пайплайна
- **ParamToggle** — сегментный контрол для toggle-параметров (glow_style)
- **Advanced Mode** — чекбокс для отображения технических параметров
- **Pin Face Oval** — кнопка-пин для фиксации овала лица
- **Dither Preview** — кнопка для предпросмотра Jarvis дизеринга (laser_80w)
- Скругление: `rounded-lg` (8px) — единообразно для всех интерактивных элементов. `rounded` (4px) и `rounded-md` (6px) не используются; `rounded-full` — исключение для аватаров/точек статуса

#### 7.2 Slider-компонент

`components/slider.tsx` — кастомный Slider с визуальным заполнением трека и опциональной кнопкой сброса.

**API:**

```tsx
interface SliderProps {
  label: string;       // Текст лейбла
  value: number;       // Текущее значение
  min: number;         // Минимум
  max: number;         // Максимум
  step: number;        // Шаг
  unit?: string;       // Единица измерения (%, мм и т.д.)
  overridden?: boolean; // Параметр изменён вручную — показать кнопку сброса
  onChange: (value: number) => void;
  onReset?: () => void; // Коллбек сброса к значению пресета
}
```

**Особенности:**
- `.slider-fill` div отображает заполненную часть трека (ширина = процент от min к max)
- При `overridden=true` отображается иконка `ri-arrow-go-back-line` для сброса
- ARIA: `role="slider"`, `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, `aria-label`

#### 7.3 Granite CRM

- **Sidebar (240px)** — навигация
- **Data Tables** — компактные, без зебры
- **Side Panel (Sheet)** — детальная информация
- **Funnel Chart** — воронка продаж

### 8. ARIA-паттерны

| Компонент | Роль | Атрибуты |
|:---|:---|:---|
| MachineSelector trigger | `button` | `aria-expanded`, `aria-haspopup="listbox"`, `id="machine-selector-trigger"` |
| MachineSelector dropdown | `listbox` | `aria-labelledby="machine-selector-trigger"` |
| MachineSelector option | `option` | `aria-selected` |
| ModuleSwitch button | `button` | `aria-pressed` |
| MaterialSelector chip | `button` | `aria-pressed`, `aria-label="Материал: {название}"` |
| StepSelector active step | `button` | `aria-current="step"` |
| ParamsPanel tab list | `tablist` | — |
| ParamsPanel tab | `tab` | `aria-selected`, `aria-controls`, `id` |
| ParamsPanel tabpanel | `tabpanel` | `aria-labelledby`, `id` |
| ParamsPanel toggle | `button` | `aria-pressed` |
| Slider | `slider` | `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, `aria-label` |

### 9. Toast-система

Единый toast-провайдер — `components/toast-provider.tsx`. Контекст + `useToast` hook.

**API:**

```ts
interface ToastOptions {
  type?: 'info' | 'error' | 'warning';   // default: 'info'
  duration?: number;                       // default: 3000 (ms)
}

function showToast(message: string, options?: ToastOptions): void;
```

**Маппинг таймаутов:**

| Источник | Вызов |
|:---|:---|
| `App.tsx` (ошибка дизеринга) | `showToast(msg, { type: 'error', duration: 3000 })` |
| `export-buttons.tsx` (ошибка экспорта) | `showToast(msg, { type: 'error', duration: 3000 })` |
| `material-selector.tsx` (валидация) | `showToast(msg, { type: 'error', duration: 4000 })` |
| `material-selector.tsx` (автокоррекции) | `showToast(msg, { type: 'info', duration: 5000 })` |

**Оборачивание в main.tsx:** `ErrorBoundary > ToastProvider > App`. Локальный toast state удалён из всех потребителей.

### 10. Валидация файлов

Клиентская валидация в `image-upload.tsx` перед отправкой на сервер:

- **Форматы:** `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`
- **Максимальный размер:** 50 MB
- **Ошибки:** "Неподдерживаемый формат: {ext}" / "Файл слишком большой ({size} MB). Максимум: 50 MB"

### 11. Drag-оверлеи

**Face Oval Overlay** — интерактивный SVG-эллипс для ручной коррекции овала лица. 5 drag-handle (center, top, bottom, left, right) с текстовыми метками `<text>`.

- **Shift-модификатор:** при перетаскивании left/right handle с зажатым Shift — пропорциональное изменение rx и ry (иначе только rx)
- **Labels:** каждый handle имеет текстовую метку (`center`, `top`, `bottom`, `left`, `right`) шрифтом JetBrains Mono
- **Pin-механизм:** кнопка-пин фиксирует овал, блокируя автообновление из автодетекции

**Vignette Overlay** — интерактивный SVG-оверлей для настройки параметров виньетки.

- **Shift+drag top handle:** изменяет vertical_diameter (иначе — все параметры виньетки)

### 12. Рекомендации по реализации

Tailwind CSS 4, CSS-переменные для тем, сетка 4px.

### References

1. [Remix Icon](https://remixicon.com/) — основная библиотека иконок
2. [Inter Typeface](https://rsms.me/inter/) — основной шрифт
3. [Outfit Typeface](https://outfit.fontby.com/) — шрифт заголовков
4. [JetBrains Mono](https://www.jetbrains.com/lp/mono/) — моноширинный шрифт
5. [Tailwind CSS v4.0](https://tailwindcss.com/blog/tailwindcss-v4-alpha) — спецификация стилей
6. [shadcn/ui](https://ui.shadcn.com/) — компонентная база CRM
