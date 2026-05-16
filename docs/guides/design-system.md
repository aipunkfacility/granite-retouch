## Дизайн-система Granite

### 1. Общие принципы

В основе дизайн-системы лежат три ключевых принципа: **Эффективность**, **Прозрачность** и
**Надёжность**. Интерфейс не должен отвлекать пользователя; он должен служить инструментом для
быстрого принятия решений.

**Целевая аудитория:** оператор гравировочного станка, технолог. Не дизайнер. Все решения
подчинены скорости работы, читаемости и предотвращению ошибок.

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

##### 2.2.1 Дополнительные роли (не вошли в `@theme`)

| Роль | HEX | Назначение |
| :--- | :--- | :--- |
| **On Primary** | `#ffffff` | Текст/иконки на primary-фоне |
| **Muted Foreground** | `#6b7280` | muted-текст в подписях (отдельно от `--color-text-muted`) |
| **On Destructive** | `#ffffff` | Текст на destructive-фоне |
| **Ring** | `#6366f1` | Focus ring (отдельно от accent-blue для кастомизации) |

##### 2.2.2 Контрастность

| Пара | Соотношение | WCAG | Статус |
| :--- | :--- | :--- | :--- |
| `#f0f0f0` на `#1a1a1a` | 15.4:1 | AAA | ✅ |
| `#a0a0a0` на `#2a2a2a` | 6.1:1 | AA | ✅ |
| `#888888` на `#2a2a2a` | 2.9:1 | — | ⚠️ Только для не-текстовых элементов (label, dim) |
| `#f0f0f0` на `#7C8CF8` | 2.5:1 | — | ⚠️ На primary-кнопках: иконка или увеличенный текст |

#### 2.3 Granite CRM (светлая тема)

| Категория | HEX | Применение |
| :--- | :--- | :--- |
| **Background** | `#F8FAFC` | Основной фон CRM |
| **Surface** | `#FFFFFF` | Карточки, таблицы, панели |
| **Text Primary** | `#0F172A` | Ink Blue — заголовки, основной текст |
| **Text Muted** | `#64748B` | Slate Gray — подписи, второстепенная информация |

#### 2.4 Карта CSS-переменных (с Tailwind-алиасами)

```css
@theme {
  /* Backgrounds */
  --color-bg-primary: #1a1a1a;
  --color-bg-secondary: #222222;
  --color-bg-card: #2a2a2a;
  --color-bg-input: #333333;
  --color-bg-hover: #3a3a3a;

  /* Text */
  --color-text-primary: #f0f0f0;
  --color-text-secondary: #a0a0a0;
  --color-text-muted: #888888;

  /* Accents */
  --color-accent-blue: #7C8CF8;
  --color-accent-primary-light: #5B6ABF;
  --color-accent-green: #10B981;
  --color-accent-orange: #F59E0B;
  --color-accent-red: #E11D48;

  /* Borders */
  --color-border: #3a3a3a;
  --color-border-focus: #7C8CF8;

  /* Radii */
  --radius: 8px;
}
```

Использование: `bg-bg-card`, `text-text-primary`, `border-border`, `bg-accent-blue`.

### 3. Типографика

**Гарнитуры:**
- **Заголовки:** Outfit, Semibold (600), letter-spacing -0.02em
- **Основной текст:** Inter, Regular (400), line-height 1.5
- **Моноширинный:** JetBrains Mono, Regular (400), 13px (ID/код, числовые значения слайдеров)

#### Modular scale (коэффициент 1.25 — Major Third)

| Токен | Размер | Weight | line-height | Применение |
| :--- | :--- | :--- | :--- | :--- |
| `--text-xs` | 0.75rem / 12px | 400 | 1.4 | Подписи, метки |
| `--text-sm` | 0.875rem / 14px | 400 | 1.5 | Body text |
| `--text-base` | 1rem / 16px | 400 | 1.5 | Крупный body |
| `--text-lg` | 1.125rem / 18px | 600 | 1.3 | Subheadings |
| `--text-xl` | 1.25rem / 20px | 600 | 1.2 | H3 |
| `--text-2xl` | 1.5rem / 24px | 600 | 1.2 | H2 |
| `--text-3xl` | 1.875rem / 30px | 600 | 1.2 | H1 |

### 4. Spacing Scale

Семантические токены отступов. Сетка 4px.

| Токен | Значение | Применение |
| :--- | :--- | :--- |
| `--space-xs` | 4px | gap между иконкой и текстом |
| `--space-sm` | 8px | Паддинги label+value, chip gaps |
| `--space-md` | 16px | Card padding |
| `--space-lg` | 24px | Section padding |
| `--space-xl` | 32px | Отступы между панелями сайдбара |
| `--space-2xl` | 48px | Margins секций |
| `--space-3xl` | 64px | Hero padding |

### 5. Shadow System

| Токен | Значение | Применение |
| :--- | :--- | :--- |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.3)` | Карточки параметров |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.4)` | Dropdown'ы, MachineSelector |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.5)` | Модальные окна |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.6)` | Тосты, `position: fixed` |

На тёмном фоне тени незаметны при малой opacity — значения подняты относительно светлой темы.

### 6. Иконки

**Remix Icon** (`ri-*`) — основная библиотека иконок для Granite Retouch и CRM. Контурные.

| Размер | Применение |
| :--- | :--- |
| 16px | Inline-иконки рядом с текстом |
| 20px | Кнопки, точки статуса |
| 24px | Пустые состояния, логотип |

**SVG-спрайт:** `public/icons.svg` (Bluesky, Discord, GitHub, X, documentation, social).

### 7. Анимации

| Элемент | Свойство | Длительность | Кривая |
| :--- | :--- | :--- | :--- |
| Hover (все clickable) | `opacity` / `border-color` | 200ms | ease |
| Active / Pressed | `scale(0.97)` | 100ms | ease-out |
| Тосты appear | `opacity` + `translateY` | 300ms | ease-out |
| Advanced params collapse | `max-height` | 250ms | ease |
| Spinner | `rotate` (CSS) | 1s | linear (infinite) |

Все интерактивные элементы получают `transition-all duration-200`.

### 8. Запрещённые паттерны

1. Классы `*-50`, `*-100`, `*-200` из стандартной палитры Tailwind запрещены для тёмной темы
   Granite Retouch. Эти классы предназначены для светлых фонов и на тёмной теме выглядят
   неестественно. Использовать только `--color-accent-*/N` (с opacity) и `--color-bg-*`.

   **Запрещено:**
   ```tsx
   <div className="bg-yellow-50 text-yellow-700 border-yellow-200" />
   ```

   **Правильно:**
   ```tsx
   <div className="bg-accent-orange/10 text-accent-orange border-accent-orange/30" />
   ```

2. `outline: none` без альтернативы — обязателен `:focus-visible`.

3. Жёстко закодированные hex вместо CSS-переменных.

4. `var()` обёртка вместо прямого использования Tailwind theme colors — писать `bg-accent-blue`,
   а не `bg-[var(--color-accent-blue)]`.

5. `scale()` в hover, если он вызывает layout shift — использовать `translateY` или `opacity`.

6. **Эмодзи как иконки** — использовать SVG (Remixicon, Heroicons, Simple Icons).

7. **Missing `cursor-pointer`** — все clickable элементы.

### 9. MACHINE_THEME

Единый источник тем станков — `lib/machine-theme.ts`. Экспортирует
`MACHINE_THEME: Record<MachineType, MachineTheme>` с полями `bg`, `border`, `dot`, `icon`,
`label`.

| MachineType | bg | border | dot | icon | label |
|:---|:---|:---|:---|:---|:---|
| `impact` | `bg-accent-orange/10` | `border-accent-orange/30` | `bg-accent-orange` | `ri-contrast-2-line` | Ударный |
| `laser_standard` | `bg-accent-green/10` | `border-accent-green/30` | `bg-accent-green` | `ri-flashlight-line` | CO2 40W |
| `laser_80w` | `bg-accent-red/10` | `border-accent-red/30` | `bg-accent-red` | `ri-flashlight-fill` | Диод 80W |

Устаревший `MACHINE_COLORS` удалён — использовать `MACHINE_THEME`.

### 10. Компоненты

#### 10.1 Granite Retouch

- **Sidebar (320px)** — параметры, диагностика, настройки станка
- **Image Preview** — before/after компаратор
- **Slider** — кастомный range input с заполнением трека и иконкой сброса (см. 10.2)
- **Step Selector** — кнопки шагов пайплайна
- **ParamToggle** — сегментный контрол для toggle-параметров (glow_style)
- **Advanced Mode** — чекбокс для отображения технических параметров
- **Pin Face Oval** — кнопка-пин для фиксации овала лица
- **Dither Preview** — кнопка для предпросмотра Jarvis дизеринга (laser_80w)
- Скругление: `rounded-lg` (8px) — единообразно для всех интерактивных элементов. `rounded` (4px)
  и `rounded-md` (6px) не используются; `rounded-full` — исключение для аватаров/точек статуса

#### 10.2 Slider-компонент

`components/slider.tsx` — кастомный Slider с визуальным заполнением трека и опциональной кнопкой
сброса.

**API:**

```tsx
interface SliderProps {
  label: string;        // Текст лейбла
  value: number;        // Текущее значение
  min: number;          // Минимум
  max: number;          // Максимум
  step: number;         // Шаг
  unit?: string;        // Единица измерения (%, мм и т.д.)
  overridden?: boolean;  // Параметр изменён вручную — показать кнопку сброса
  orientation?: 'horizontal' | 'vertical';  // Расположение label (default: horizontal)
  onChange: (value: number) => void;
  onReset?: () => void; // Коллбек сброса к значению пресета
}
```

**Особенности:**
- `.slider-fill` div отображает заполненную часть трека (ширина = процент от min к max)
- При `overridden=true` отображается иконка `ri-arrow-go-back-line` для сброса
- ARIA: `role="slider"`, `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, `aria-label`

#### 10.3 Export Buttons

`components/export-buttons.tsx`

```tsx
interface ExportButtonsProps {
  fileId: string;
  machineType: MachineType;
  disabled?: boolean;
}
```

- Primary button: формат зависит от `machineType` (bmp_8bit для laser_80w/impact, bmp для
  laser_standard)
- Secondary PNG button (для превью)
- Dropdown с additional formats: BMP, BMP 8-bit, BMP 1-bit, TIFF
- Loading state per format

#### 10.4 Machine Selector

`components/machine-selector.tsx`

- Grouped dropdown: combo groups (SAUNO, Stanzone, Mirtels) → brand groups → "По технологии"
- Keyboard navigation: Arrow keys, Enter, Escape, Tab (focus trap)
- Color-coded dots по `MACHINE_THEME`
- `role="listbox"`, `aria-expanded`, `aria-selected`

#### 10.5 Material Selector

`components/material-selector.tsx`

- 5 chips: Гранит, Габбро, Базальт, Мрамор, Акрил
- **normal** — `rounded-full` чип
- **warn** — желтая рамка `border-accent-orange/30`
- **incompatible** — красная рамка `border-accent-red/30` + тост об ошибке
- При смене материала — автокоррекция параметров конфига

#### 10.6 Granite CRM

- **Sidebar (240px)** — навигация
- **Data Tables** — компактные, без зебры
- **Side Panel (Sheet)** — детальная информация
- **Funnel Chart** — воронка продаж

### 11. ARIA-паттерны

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
| VignetteOverlay handle | `button` | `aria-label="Vignette {position} handle"` |
| FaceOvalOverlay handle | `button` | `aria-label="Face oval {position} handle"` |

### 12. Toast-система

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

**Оборачивание в main.tsx:** `ErrorBoundary > ToastProvider > App`. Локальный toast state удалён
из всех потребителей.

### 13. Валидация файлов

Клиентская валидация в `image-upload.tsx` перед отправкой на сервер:

- **Форматы:** `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`
- **Максимальный размер:** 50 MB
- **Ошибки:** "Неподдерживаемый формат: {ext}" / "Файл слишком большой ({size} MB). Максимум: 50 MB"

### 14. Drag-оверлеи

**Face Oval Overlay** — интерактивный SVG-эллипс для ручной коррекции овала лица. 5 drag-handle
(center, top, bottom, left, right) с текстовыми метками `<text>`.

- **Shift-модификатор:** при перетаскивании left/right handle с зажатым Shift — пропорциональное
  изменение rx и ry (иначе только rx)
- **Labels:** каждый handle имеет текстовую метку (`center`, `top`, `bottom`, `left`, `right`)
  шрифтом JetBrains Mono
- **Pin-механизм:** кнопка-пин фиксирует овал, блокируя автообновление из автодетекции

**Vignette Overlay** — интерактивный SVG-оверлей для настройки параметров виньетки.

- **Shift+drag top handle:** изменяет vertical_diameter (иначе — все параметры виньетки)

### 15. Как сверять документ с кодом

| Файл | Сверять с секцией |
| :--- | :--- |
| `index.css` (`@theme { ... }`) | 2.4 — карта CSS-переменных |
| `lib/machine-theme.ts` | 9 — MACHINE_THEME |
| `components/*.tsx` (пропсы) | 10 — компонентные API |

### References

1. [Remix Icon](https://remixicon.com/) — основная библиотека иконок
2. [Inter Typeface](https://rsms.me/inter/) — основной шрифт
3. [Outfit Typeface](https://outfit.fontby.com/) — шрифт заголовков
4. [JetBrains Mono](https://www.jetbrains.com/lp/mono/) — моноширинный шрифт
5. [Tailwind CSS v4.0](https://tailwindcss.com/blog/tailwindcss-v4-alpha) — спецификация стилей
6. [shadcn/ui](https://ui.shadcn.com/) — компонентная база CRM
