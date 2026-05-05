# Pre-0: Быстрые исправления

**Предыдущий этап**: нет
**Следующий этап**: [Фаза 0](dev-plan-phase0-pipeline.md)
**Время**: ~1 час
**Цель**: Устранить баги и рассинхронизации до начала рефакторинга. Эти исправления не затрагивают архитектуру — это чистые баг-фиксы.

---

## Задачи

### 1. Исправить баг в fringe-тесте

**Файл**: `tests/test_chromakey.py`
**Строка**: ~91
**Проблема**: Переменной `arr_with_fringe` присваивается `result_no_fringe` вместо `result_with_fringe`. Тест сравнивает массив сам с собой — всегда проходит.

**Было**:
```python
result_with_fringe, _ = remove_blue_background(img, threshold=30, fringe_radius=3)
arr_with_fringe = np.array(result_no_fringe)  # БАГ
```

**Стало**:
```python
result_with_fringe, _ = remove_blue_background(img, threshold=30, fringe_radius=3)
arr_with_fringe = np.array(result_with_fringe)  # ИСПРАВЛЕНО
```

**Проверка**: Запустить `pytest tests/test_chromakey.py::test_fringe_reduces_blue_artifacts -v`. Тест должен проходить, и `blue_with.mean()` должен быть меньше `blue_no.mean()` (fringe removal реально уменьшает синие артефакты). Если тест падает после исправления — баг в самом fringe removal, а не только в тесте.

---

### 2. Синхронизировать версию в `__init__.py`

**Файл**: `retouch/__init__.py`
**Проблема**: `__version__ = "2.3.1"` при `pyproject.toml` версии `2.6.0`

**Было**:
```python
__version__ = "2.3.1"
```

**Стало**:
```python
__version__ = "2.6.0"
```

**Дополнительно**: Обновить `uv.lock` командой `uv lock` из корня проекта.

---

### 3. Синхронизировать DEFAULTS и config.yaml

**Файлы**: `retouch/config.py`, `config.yaml`
**Проблема**: `laser.brightness` в DEFAULTS = 1.05, в config.yaml = 1.18. Поведение зависит от наличия config.yaml.

**Решение**: Привести DEFAULTS к значениям config.yaml (1.18 — проверенное рабочее значение). Config.yaml — источник истины, DEFAULTS должен совпадать.

**Изменения в `retouch/config.py`**:
```python
# Было:
"brightness": 1.05,

# Стало:
"brightness": 1.18,
```

**Проверка**: Удалить/переименовать config.yaml временно. Запустить `pytest tests/`. Тесты используют DEFAULTS — должны проходить с brightness=1.18.

---

### 4. Убрать shadow_noise из конфига

**Файлы**: `retouch/config.py`, `config.yaml`, `docs/guides/style-guide-impact.md`, `docs/reference/config.md`
**Проблема**: `impact.shadow_noise: true` существует в конфиге и документации, но не реализован в коде. Дезинформация пользователя.

**Решение**: Убрать параметр из DEFAULTS и config.yaml. В документации заменить на заметку: «shadow_noise: планируемая функция (BACKLOG-006)». Если параметр будет реализован позже — он вернётся в конфиг с рабочим кодом в тот же коммит.

**Изменения**:

`retouch/config.py` — убрать из DEFAULTS:
```python
# Удалить строку:
"shadow_noise": True,
```

`config.yaml` — убрать:
```yaml
# Удалить:
shadow_noise: true
```

---

### 5. Удалить GIMP-пайплайн из основной ветки

**Файлы**: `retouch/gimp/`, `retouch_process.scm`
**Проблема**: Мёртвый код, не синхронизированный с Python-пайплайном. Занимает ментальную полосу при ревью.

**Решение**:
1. Создать ветку `experimental/gimp` и закоммитить туда текущее состояние
2. Удалить `retouch/gimp/` и `retouch_process.scm` из main
3. Убрать `gimp` из CLI-команд в `retouch/cli.py`
4. Убрать `gimp`-цели из `Makefile`
5. Добавить в `docs/architecture/overview.md` заметку: «GIMP-пайплайн не поддерживается. Историческая реализация доступна в ветке experimental/gimp»

---

## Чеклист приёмки

- [ ] `pytest tests/` — все тесты проходят
- [ ] `pytest tests/test_chromakey.py::test_fringe_reduces_blue_artifacts -v` — тест реально проверяет fringe removal
- [ ] `retouch.__version__` == версия в `pyproject.toml`
- [ ] `uv.lock` обновлён
- [ ] DEFAULTS["processing"]["laser"]["brightness"] == config.yaml laser.brightness
- [ ] `shadow_noise` нет в DEFAULTS и config.yaml
- [ ] `retouch/gimp/` не существует в main
- [ ] `retouch_process.scm` не существует в main
- [ ] `retouch gimp` команда убрана из CLI
- [ ] Документация обновлена

---

## Примечания для агента

- Все изменения — в существующих файлах, новых файлов нет
- После выполнения — запустить `pytest tests/ -v` для подтверждения
- Ветка `experimental/gimp` создаётся до удаления файлов из main
