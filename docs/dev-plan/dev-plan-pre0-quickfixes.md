# Pre-0: Быстрые исправления

**Предыдущий этап**: нет
**Следующий этап**: [Фаза 0](dev-plan-phase0-pipeline.md)
**Время**: ~1 час
**Цель**: Устранить баги и рассинхронизации до начала рефакторинга. Эти исправления не затрагивают архитектуру — это чистые баг-фиксы.

---

## Задачи

### 1. Исправить баг в fringe-тесте

**Файл**: `tests/test_chromakey.py`
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

**Проверка**: `pytest tests/test_chromakey.py::test_fringe_reduces_blue_artifacts -v`. Если тест падает после исправления — баг в самом fringe removal.

---

### 2. Поднять версию до 3.0.0-dev (A10)

**Файлы**: `retouch/__init__.py`, `pyproject.toml`
**Обоснование**: План вводит Breaking Changes (новая сигнатура `check_face_brightness()`, изменение поведения `load_config()`). По SemVer — major-версия.

**retouch/__init__.py**:
```python
__version__ = "3.0.0-dev"
```

**pyproject.toml**:
```toml
version = "3.0.0-dev"
```

**Обязательно**: После исправления запустить `uv lock` из корня проекта для обновления lock-файла.

---

### 3. Синхронизировать DEFAULTS и config.yaml (A1 — частично)

**Файлы**: `retouch/config.py`, `config.yaml`
**Проблема**: `laser.brightness` в DEFAULTS = 1.05, в config.yaml = 1.18. Новые параметры `face_region_top` и `highlight_start` отсутствуют в обоих.

**Решение**:
1. Привести DEFAULTS к значениям config.yaml (1.18 — проверенное рабочее значение)
2. Добавить `face_region_top` и `highlight_start` в DEFAULTS и config.yaml (A1)

**Изменения в `retouch/config.py`**:
```python
# Было:
"brightness": 1.05,

# Стало:
"brightness": 1.18,

# Добавить в laser и impact:
"face_region_top": 0.45,
"highlight_start": 200,
```

**Изменения в `config.yaml`**:
```yaml
laser:
  # ... существующие параметры ...
  face_region_top: 0.45
  highlight_start: 200

impact:
  # ... существующие параметры ...
  face_region_top: 0.45
  highlight_start: 200
```

**Проверка**: Удалить/переименовать config.yaml временно. Запустить `pytest tests/`. Тесты используют DEFAULTS — должны проходить с brightness=1.18.

---

### 4. Убрать shadow_noise из конфига

**Файлы**: `retouch/config.py`, `config.yaml`, `docs/guides/style-guide-impact.md`, `docs/reference/config.md`, `tests/test_config.py`
**Проблема**: `impact.shadow_noise: true` существует в конфиге и документации, но не реализован в коде. Дезинформация пользователя.

**Решение**: Убрать параметр из DEFAULTS и config.yaml. В документации заменить на заметку: «shadow_noise: планируемая функция (BACKLOG-006)».

**retouch/config.py** — убрать из DEFAULTS:
```python
# Удалить строку:
"shadow_noise": True,
```

**config.yaml** — убрать:
```yaml
# Удалить:
shadow_noise: true
```

**tests/test_config.py** — обновить:
```python
# Было:
assert "shadow_noise" in impact

# Стало:
assert "shadow_noise" not in impact  # BACKLOG-006: не реализован
```

---

### 5. GIMP-пайплайн — пометка experimental (сохраняется!)

**Файлы**: `retouch/gimp/runner.py`, `retouch/cli.py`
**Решение BACKLOG-005**: Пометить как experimental / not recommended. GIMP-пайплайн **не удаляется**.

> ⚠ **Внимание**: Это подтверждает оригинальное решение BACKLOG-005. Задача Pre-0 №5 из v3.3 (удаление GIMP) **отменена**.

**Изменения**:

`retouch/cli.py` — предупреждение уже добавлено в текущем коде:
```python
def cmd_gimp(args):
    """GIMP-обработка портрета (experimental / not recommended)."""
    print("⚠ Experimental: results may be incorrect. "
          "Use `retouch process` for production.", file=sys.stderr)
```

Дополнительно — добавить в help CLI:
```python
p_gimp = subparsers.add_parser(
    "gimp",
    help="GIMP-обработка (experimental / не рекомендуется для production)"
)
```

Дополнительных изменений не требуется — предупреждение уже есть в коде.

---

### 6. Запустить `uv lock`

**Проблема**: `uv.lock` содержит версию 2.3.1 (устарел). После обновления версии (задача 2) нужно обновить lock-файл.

```bash
cd /path/to/granite-retouch
uv lock
```

---

### 7. Обновить BACKLOG.md (A8)

Отметить задачи, которые закрывает Pre-0:

```markdown
### BACKLOG-003: Убрать отладочный вывод из production-кода
**Статус**: Partial — будет завершено в Фазе 0 (задача 6)

### BACKLOG-004: Синхронизировать defaults в config.py и config.yaml
**Статус**: ✅ Done (Pre-0, задача 3)

### BACKLOG-005: GIMP-пайплайн — исправить или удалить
**Статус**: ✅ Done — пометка experimental (Pre-0, задача 5)

### BACKLOG-006: Shadow noise для impact
**Статус**: Partial — shadow_noise убран из конфига (Pre-0, задача 4), реализация — будущая задача
```

---

## Порядок выполнения

1. Задача 1 (fringe-тест)
2. Задача 2 (версия → 3.0.0-dev)
3. Задача 3 (DEFAULTS ← config.yaml + face_region_top + highlight_start)
4. Задача 4 (shadow_noise + обновление test_config.py)
5. Задача 5 (GIMP — пометка experimental, НЕ удаление)
6. Задача 6 (uv lock)
7. Задача 7 (обновить BACKLOG.md)
8. `pytest tests/ -v` — все тесты проходят
9. `git tag pre0-done`

---

## Чеклист приёмки

- [ ] `pytest tests/ -v` — все тесты проходят
- [ ] `pytest tests/test_chromakey.py::test_fringe_reduces_blue_artifacts -v` — тест реально проверяет fringe removal
- [ ] `retouch.__version__` == версия в `pyproject.toml` == `3.0.0-dev`
- [ ] `uv.lock` обновлён
- [ ] DEFAULTS["processing"]["laser"]["brightness"] == config.yaml laser.brightness == 1.18
- [ ] `face_region_top` и `highlight_start` присутствуют в DEFAULTS и config.yaml
- [ ] `shadow_noise` нет в DEFAULTS и config.yaml
- [ ] Тест `test_config.py` обновлён — не проверяет `shadow_noise`
- [ ] `retouch/gimp/` существует в main — **не удалён**
- [ ] `retouch_process.scm` существует — **не удалён**
- [ ] `retouch gimp` команда работает и показывает предупреждение «experimental»
- [ ] BACKLOG.md обновлён
- [ ] Git-тег `pre0-done` создан
