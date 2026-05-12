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
| **Text Muted** | `#666666` | `--color-text-muted` |
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
- **Моноширинный:** JetBrains Mono, 13px (для ID/кода)

### 4. Иконки

**Remix Icon** (`ri-*`) — основная библиотека иконок для Granite Retouch и CRM. Контурные, размер 16-20px.

### 5. Компоненты

#### 5.1 Granite Retouch

- **Sidebar (320px)** — параметры, диагностика, настройки станка
- **Image Preview** — before/after компаратор
- **Sliders** — range input с тёмной темой
- **Step Selector** — кнопки шагов пайплайна
- **ParamToggle** — сегментный контрол для toggle-параметров (glow_style)
- **Advanced Mode** — чекбокс для отображения технических параметров
- **Pin Face Oval** — кнопка-пин для фиксации овала лица
- **Dither Preview** — кнопка для предпросмотра Jarvis дизеринга (laser_80w)
- Скругление: `radius-md` (8px)

#### 5.2 Granite CRM

- **Sidebar (240px)** — навигация
- **Data Tables** — компактные, без зебры
- **Side Panel (Sheet)** — детальная информация
- **Funnel Chart** — воронка продаж

### 6. Рекомендации по реализации

Tailwind CSS 4, CSS-переменные для тем, сетка 4px.

### References

1. [Remix Icon](https://remixicon.com/) — основная библиотека иконок
2. [Inter Typeface](https://rsms.me/inter/) — основной шрифт
3. [Outfit Typeface](https://rsms.me/inter/) — шрифт заголовков
4. [Tailwind CSS v4.0](https://tailwindcss.com/blog/tailwindcss-v4-alpha) — спецификация стилей
5. [shadcn/ui](https://ui.shadcn.com/) — компонентная база CRM
