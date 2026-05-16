# granite-retouch Web UI (Frontend)

Интерактивный интерфейс настройки параметров ретуши с живым предпросмотром.

## Стек

- **React 19** + **TypeScript**
- **Vite** — dev-сервер и сборка
- **Tailwind CSS 4** — стилизация
- **shadcn/ui** — компоненты

## Запуск

```bash
npm install       # зависимости (один раз)
npm run dev       # dev-сервер на http://localhost:5173
npm run build     # production-сборка в dist/
```

Vite проксирует запросы `/api/*` на backend `http://localhost:8000`.

## Лейаут (Portrait Split)

```
┌──────────────────────────────────────────────────┐
│ Header: Logo | Machine | Material | Overlays | Export │
├──────────────┬───────────────────────────────────┤
│ Step Bar: Шаги | Дизеринг | Сменить фото          │
├──────────────┼───────────────────────────────────┤
│ Left Column  │ Canvas                            │
│ (360px)      │                                   │
│              │                                   │
│ BeforeImage  │   AfterImage                      │
│              │   (loading/error/empty states)     │
│ ParamsPanel  │   + overlays (vignette, oval)     │
│ (accordions) │                                   │
│              │                                   │
│ ConfigActions│                                   │
│ Diagnostics  │                                   │
└──────────────┴───────────────────────────────────┘
```

## Возможности

- Загрузка изображения через drag & drop
- Живой предпросмотр при изменении параметров (слайдеры)
- Переключение станка laser_standard / laser_80w / impact
- Пресеты (готовые наборы параметров из `presets/`)
- Экспорт BMP/PNG/TIFF в полном разрешении
- FaceOval overlay — интерактивная коррекция овала лица (4 drag handles)
- Vignette overlay — настройка арховой виньетки

## Горячие клавиши

| Клавиша | Действие |
|---------|----------|
| `P` / `З` | Свернуть/развернуть блок параметров |
| `[` / `Х` | Скрыть/показать левую колонку |
| `Escape` | Выйти из режима «Сравнить» |

## Архитектура компонентов

Подробнее: [DEVELOPMENT.md](DEVELOPMENT.md)

 Подробнее: [docs/guides/webui-setup.md](../../docs/guides/webui-setup.md)
