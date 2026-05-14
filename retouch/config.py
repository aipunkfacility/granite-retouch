"""Загрузка и валидация конфигурации из config.yaml.

Схема конфига (v4):
  - config_version: 4 — для цепочки миграций (v0→v1→v2→v3→v4)
  - processing.{machine}.export_mode: "8bit" | "1bit" — режим экспорта BMP
  - processing.{machine}.step_mm: шаг ЧПУ в мм (per-machine, с v3)
  - processing.{machine}.dither_method_1bit: метод дизеринга для 1-bit режима
  - processing.{machine}.dither_method: DEPRECATED, заменён на export_mode + dither_method_1bit
  - machine.step_mm: 0.300 — глобальный fallback (обратная совместимость)
  - stone.material: тип материала (granite|marble|gabbro|basalt|acrylic) — НОВОЕ в v4
  - stone.type: DEPRECATED, alias для stone.material (удаление в v5)

Миграции:
  v0→v1: face_brightness_target list→min/max, laser→laser_standard, brightness→stone_gamma
  v1→v2: добавление config_version=2
  v2→v3: dither_method→export_mode, global step_mm→per-machine, laser_80w gamma/fb
  v3→v4: stone.type→material (alias, оба ключа записываются)
"""

import copy
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Все допустимые значения machine_type
MACHINE_TYPES = ("laser_standard", "laser_80w", "impact")

# Профили материалов (бывший STONE_PROFILES — переименован в v4)
# Расширен: добавлены step_mm_range, stone_gamma_range, shadow_floor, white_ceiling_offset,
# export_mode_override, dither_method_override, incompatible_machine_types
MATERIAL_PROFILES = {
    "granite": {
        "heterogeneity": 2.0,
        "step_mm_range": (0.250, 0.300),
        "stone_gamma_range": (0.85, 0.90),
        "shadow_floor": 8,
        "white_ceiling_offset": 0,
        "notes": "Крупнозернистый — «съедает» контраст. Переконтрастированная ретушь.",
        "hints": {
            "laser_80w": "white_ceiling \u2264 235 — при 80W значения > 235 пережигаются",
        },
    },
    "gabbro": {
        "heterogeneity": 1.0,
        "step_mm_range": (0.275, 0.350),
        "stone_gamma_range": (0.88, 0.92),
        "shadow_floor": 8,
        "white_ceiling_offset": 0,
        "notes": "Лучший камень для портретов. Тёмный фон = хороший контраст. "
                 "Mirtels: 85 dpi + 2 прохода для габбро-диабаза.",
    },
    "basalt": {
        "heterogeneity": 1.5,
        "step_mm_range": (0.225, 0.275),
        "stone_gamma_range": (0.88, 0.90),
        "shadow_floor": 8,
        "white_ceiling_offset": 0,
        "notes": "Мелкозернистый — хорошо для детальных портретов. САУНО: шаг 0.225.",
    },
    "marble": {
        "heterogeneity": 3.0,
        "step_mm_range": (0.350, 0.400),
        "stone_gamma_range": (0.92, 1.0),
        "shadow_floor": 5,
        "white_ceiling_offset": -5,
        "notes": "Мягкий, хрупкий. Лазер предпочтительнее ударного. "
                 "Точки сливаются при мелком шаге — увеличивать step_mm.",
        "hints": {
            "impact": "Мрамор хрупкий — лазер предпочтительнее ударного",
        },
        "warnings": ["impact+marble"],
    },
    "acrylic": {
        "heterogeneity": 0.0,
        "step_mm_range": (0.127, 0.150),
        "stone_gamma_range": (0.88, 1.0),
        "shadow_floor": 5,
        "white_ceiling_offset": 0,
        "export_mode_override": "1bit",
        "dither_method_override": "jarvis",
        "notes": "Лазерная гравировка акрила: BMP 1-bit + Jarvis/Diffusion. "
                 "200 dpi, скорость 300 мм/с. Затирка белой краской.",
        "hints": {
            "laser_80w": "BMP 1-bit + Jarvis, 200 dpi, 300 мм/с (мануал Mirtels)",
            "laser_standard": "BMP 1-bit + Jarvis, 200 dpi, 300 мм/с (мануал Mirtels)",
        },
        "incompatible_machine_types": ["impact"],
    },
}

# Backward compatibility alias
STONE_PROFILES = MATERIAL_PROFILES

DEFAULTS = {
    "config_version": 4,  # Версия схемы конфига — для цепочки миграций
    "processing": {
        "blue_threshold": 30,
        "min_blue_ratio": 0.15,
        "min_resolution": 512,
        "max_resolution": 4096,  # Защита от OOM: 4096×4096 × 4 байт = 64 MB
        "result_min_black_ratio": 0.25,
        "fringe_radius": 3,
        "mask_soft_sigma": 1.5,  # Софт-маска хромакея: 0=бинарная, 1-2=плавные края
        "legacy_step_order": False,  # A.3: rollback для нового порядка шагов
        "laser_standard": {
            "glow_size_min": 40, "glow_size_max": 80,
            "glow_opacity_min": 30, "glow_opacity_max": 40,
            "glow_style": "outer",  # A.5: inner | outer
            "stone_gamma": 0.88,  # FIX #8: SOP 5.1
            "unsharp_threshold": 3,  # FIX #11: SOP 3.1
            "shadow_floor": 5,  # FIX #12: SOP 5.1
            "target_pre_fb": 180,
            "face_brightness_target_min": 230,
            "face_brightness_target_max": 245,
            "white_ceiling": 250,
            "face_region_top": 0.45,
            "highlight_start": 200,
            "face_skin_threshold": 100,  # порог кожи: волосы < 100, кожа >= 100
            "export_mode": "8bit",  # 8-bit grayscale BMP — Engrave делает растрирование сам
            "step_mm": 0.300,  # шаг ЧПУ для laser_standard
            "dither_method_1bit": "jarvis",  # метод дизеринга если оператор переключит на 1bit
        },
        "laser_80w": {
            "glow_size_min": 15, "glow_size_max": 25,
            "glow_opacity_min": 10, "glow_opacity_max": 20,
            "glow_style": "outer",
            "stone_gamma": 1.0,  # при 8bit Engrave сам управляет яркостью через Р-график
            "unsharp_threshold": 3,  # FIX #11: SOP 3.1
            "shadow_floor": 5,  # FIX #12: SOP 5.1
            "target_pre_fb": 150,
            "face_brightness_target_min": 160,  # перекалибровка: gamma=1.0 вместо 0.85
            "face_brightness_target_max": 180,
            "white_ceiling": 235,
            "face_region_top": 0.45,
            "highlight_start": 195,
            "face_skin_threshold": 100,  # порог кожи: волосы < 100, кожа >= 100
            "export_mode": "8bit",  # 8-bit grayscale — Engrave модулирует мощность по яркости
            "step_mm": 0.250,  # по мануалу САУНО: 0.125–0.250 мм для лазера
            "dither_method_1bit": "jarvis",  # метод дизеринга если оператор переключит на 1bit
        },
        "impact": {
            "glow_size_min": 10, "glow_size_max": 25,
            "glow_opacity_min": 60, "glow_opacity_max": 80,
            "glow_style": "outer",
            "stone_gamma": 0.90,  # FIX #8: SOP 5.1
            "unsharp_threshold": 2,  # FIX #11: SOP 3.1
            "target_pre_fb": 160,
            "face_brightness_target_min": 200,
            "face_brightness_target_max": 225,
            "white_ceiling": 240,
            "face_region_top": 0.45,
            "highlight_start": 200,
            "face_skin_threshold": 100,  # порог кожи: волосы < 100, кожа >= 100
            "shadow_noise_min": 5,
            "shadow_noise_max": 15,
            "shadow_noise_threshold": 30,  # A.1: порог для shadow noise
            "shadow_floor": 8,  # A.2: минимальная яркость для impact
            "export_mode": "8bit",  # 8-bit grayscale — 256 уровней силы удара
            "step_mm": 0.300,  # шаг ЧПУ для impact
            "dither_method_1bit": "stucki",  # метод дизеринга если оператор переключит на 1bit
        },
    },
    "machine": {
        "step_mm": 0.300,  # B.2: шаг ЧПУ для расчёта BMP resolution
    },
    "stone": {
        "type": "granite",  # DEPRECATED: используйте 'material'. Alias, синхронизируется автоматически.
        "material": "granite",  # НОВОЕ v4: тип материала (камень/акрил)
        "heterogeneity": None,  # None = auto по material → MATERIAL_PROFILES
    },
    "vignette": {
        "vertical_offset": 0.10,  # FIX #3: восстановлено (было 0.30)
        "vertical_diameter": 0.55,
        "blur_radius": 60,
        "headroom": 0.6,
        "horizontal_oversize": 0.2,
    },
}

# Текущая версия схемы конфига — должна совпадать с DEFAULTS["config_version"]
CONFIG_VERSION = DEFAULTS["config_version"]


def resolve_config(processing_params: dict | None = None,
                   order_params: dict | None = None,
                   config_params: dict | None = None) -> dict:
    """B.2: Трёхуровневое разрешение параметров.

    Приоритет (от высшего к низшему):
      1. processing_params — UI / сессия (высший)
      2. order_params — order.json (средний)
      3. config_params — config.yaml (низший)

    Args:
        processing_params: параметры из UI/сессии
        order_params: параметры из order.json
        config_params: параметры из config.yaml (уже загруженный конфиг)

    Returns:
        dict: итоговый конфиг с переопределёнными значениями
    """
    base = copy.deepcopy(config_params or DEFAULTS)

    # Сливаем order.json поверх config.yaml
    if order_params:
        base = deep_merge(base, order_params)

    # Сливаем UI-параметры поверх всего
    if processing_params:
        base = deep_merge(base, processing_params)

    return base


def apply_material_overrides(config: dict, material: str) -> tuple[dict, list[dict]]:
    """Применить переопределения из MATERIAL_PROFILES к конфигу станка.

    Возвращает: (updated_config, changes)
      changes = [{"param": "step", "old": 0.300, "new": 0.350, "reason": "..."}, ...]
      — список ТОЛЬКО реально изменившихся параметров с причиной изменения.

    Логика:
    - step_mm: если текущий вне range → подогнать к ближайшей границе
    - stone_gamma: аналогично
    - shadow_floor: переопределить если задан и отличается
    - export_mode_override: для акрила — переключить на 1bit
    - dither_method_override: для акрила — переключить на jarvis
    - white_ceiling: скорректировать на offset

    Каждая корректировка логируется через logging.info() —
    при дебаге оператор видит откуда взялось значение.
    """
    changes = []

    profile = MATERIAL_PROFILES.get(material)
    if not profile:
        return config, changes

    config = copy.deepcopy(config)
    machine_type = config.get("machine_type", "laser_standard")
    mc = config.setdefault("processing", {}).setdefault(machine_type, {})

    # step_mm — подогнать к диапазону материала
    lo, hi = profile["step_mm_range"]
    current_step = mc.get("step_mm", 0.300)
    if current_step < lo:
        mc["step_mm"] = lo
        reason = f"ниже диапазона {material} ({lo:.3f}\u2013{hi:.3f})"
        changes.append({"param": "step", "old": current_step, "new": lo, "reason": reason})
        logger.info("material_override: step_mm %.3f \u2192 %.3f (%s: %s)",
                     current_step, lo, material, reason)
    elif current_step > hi:
        mc["step_mm"] = hi
        reason = f"выше диапазона {material} ({lo:.3f}\u2013{hi:.3f})"
        changes.append({"param": "step", "old": current_step, "new": hi, "reason": reason})
        logger.info("material_override: step_mm %.3f \u2192 %.3f (%s: %s)",
                     current_step, hi, material, reason)

    # stone_gamma — подогнать к диапазону материала
    glo, ghi = profile["stone_gamma_range"]
    current_gamma = mc.get("stone_gamma", 0.90)
    if current_gamma < glo:
        mc["stone_gamma"] = glo
        reason = f"ниже диапазона {material} ({glo:.2f}\u2013{ghi:.2f})"
        changes.append({"param": "gamma", "old": current_gamma, "new": glo, "reason": reason})
        logger.info("material_override: stone_gamma %.2f \u2192 %.2f (%s: %s)",
                     current_gamma, glo, material, reason)
    elif current_gamma > ghi:
        mc["stone_gamma"] = ghi
        reason = f"выше диапазона {material} ({glo:.2f}\u2013{ghi:.2f})"
        changes.append({"param": "gamma", "old": current_gamma, "new": ghi, "reason": reason})
        logger.info("material_override: stone_gamma %.2f \u2192 %.2f (%s: %s)",
                     current_gamma, ghi, material, reason)

    # shadow_floor — переопределить
    if "shadow_floor" in profile:
        old_floor = mc.get("shadow_floor", 5)
        mc["shadow_floor"] = profile["shadow_floor"]
        if old_floor != profile["shadow_floor"]:
            changes.append({"param": "shadow_floor", "old": old_floor, "new": profile["shadow_floor"]})
            logger.info("material_override: shadow_floor %d \u2192 %d (%s)",
                         old_floor, profile["shadow_floor"], material)

    # white_ceiling — скорректировать
    if profile.get("white_ceiling_offset", 0):
        default_ceiling = mc.get("white_ceiling", 240)
        new_ceiling = max(100, min(255, default_ceiling + profile["white_ceiling_offset"]))
        mc["white_ceiling"] = new_ceiling
        if new_ceiling != default_ceiling:
            changes.append({"param": "white_ceiling", "old": default_ceiling, "new": new_ceiling})
            logger.info("material_override: white_ceiling %d \u2192 %d (%s: offset %d)",
                         default_ceiling, new_ceiling, material, profile["white_ceiling_offset"])

    # export_mode_override — акрил = 1bit
    if profile.get("export_mode_override"):
        old_mode = mc.get("export_mode", "8bit")
        mc["export_mode"] = profile["export_mode_override"]
        changes.append({"param": "export_mode", "old": old_mode, "new": profile["export_mode_override"]})
        logger.info("material_override: export_mode %s \u2192 %s (%s)",
                     old_mode, profile["export_mode_override"], material)
    if profile.get("dither_method_override"):
        old_dither = mc.get("dither_method_1bit", "none")
        mc["dither_method_1bit"] = profile["dither_method_override"]
        changes.append({"param": "dither", "old": old_dither, "new": profile["dither_method_override"]})
        logger.info("material_override: dither_method_1bit \u2192 %s (%s)",
                     profile["dither_method_override"], material)

    return config, changes


# Backward compatibility alias
apply_stone_overrides = apply_material_overrides


def validate_machine_material(machine_type: str, material: str) -> list[str]:
    """Проверить совместимость станка и материала.

    Возвращает список предупреждений/ошибок.
    Пустой список = всё OK.
    """
    profile = MATERIAL_PROFILES.get(material, {})
    warnings = []

    # Жёсткая несовместимость: акрил + ударный
    if machine_type in profile.get("incompatible_machine_types", []):
        warnings.append(
            f"ERROR: {material} не поддерживает ударную гравировку. "
            f"Используйте лазерный модуль."
        )

    # Предупреждение: мрамор + ударный
    if machine_type == "impact" and material == "marble":
        warnings.append(
            "WARNING: Мрамор хрупкий — лазер предпочтительнее ударного."
        )

    # Предупреждение: 80W + гранит (пережигание)
    if machine_type == "laser_80w" and material == "granite":
        warnings.append(
            "WARNING: white_ceiling \u2264 235 — при 80W значения > 235 пережигаются."
        )

    return warnings


# --- Pydantic модели ---

try:
    from pydantic import BaseModel, Field, field_validator, model_validator

    class MachineConfig(BaseModel):
        glow_size_min: int = Field(40, ge=5, le=100)
        glow_size_max: int = Field(80, ge=5, le=100)
        glow_opacity_min: int = Field(30, ge=10, le=100)
        glow_opacity_max: int = Field(40, ge=10, le=100)
        glow_style: str = Field("outer", pattern="^(inner|outer)$")

        @field_validator("glow_style", mode="before")
        @classmethod
        def _coerce_glow_style(cls, v):
            """Accept int 0/1 from legacy frontend toggle (0=outer, 1=inner)."""
            if isinstance(v, int):
                return "inner" if v else "outer"
            return v
        stone_gamma: float = Field(0.88, ge=0.5, le=1.5)  # FIX #8
        unsharp_threshold: int = Field(3, ge=0, le=20)  # FIX #11: SOP 3.1
        target_pre_fb: int = Field(160, ge=60, le=220)
        face_brightness_target_min: int = Field(230, ge=80, le=255)
        face_brightness_target_max: int = Field(245, ge=80, le=255)
        white_ceiling: int = Field(250, ge=100, le=255)
        face_region_top: float = Field(0.45, ge=0.2, le=0.8)
        highlight_start: int = Field(200, ge=80, le=250)
        shadow_noise_min: int = Field(0, ge=0, le=50)
        shadow_noise_max: int = Field(15, ge=0, le=50)
        shadow_noise_threshold: int = Field(30, ge=5, le=80)
        shadow_floor: int = Field(5, ge=0, le=30)  # FIX #12: default 5 (SOP 5.1)
        dither_method: str = Field("none", pattern="^(none|floyd_steinberg|jarvis|stucki)$")  # DEPRECATED: use export_mode + dither_method_1bit
        export_mode: str = Field("8bit", pattern="^(8bit|1bit)$")  # 8-bit grayscale or 1-bit dithered
        step_mm: float = Field(0.300, ge=0.10, le=0.50)  # per-machine CNC step in mm
        dither_method_1bit: str = Field("jarvis", pattern="^(none|jarvis|stucki)$")  # dithering for 1bit mode
        # Backward compat: accept old list format
        face_brightness_target: list[int] | None = Field(None, exclude=True)

    class ProcessingConfig(BaseModel):
        blue_threshold: int = Field(30, ge=10, le=80)
        min_blue_ratio: float = Field(0.15, ge=0.0, le=1.0)
        fringe_radius: int = Field(3, ge=0, le=10)
        legacy_step_order: bool = Field(False)
        laser_standard: MachineConfig = Field(default_factory=lambda: MachineConfig(
            glow_size_min=40, glow_size_max=80, glow_opacity_min=30, glow_opacity_max=40,
            glow_style="outer", stone_gamma=0.88, unsharp_threshold=3, shadow_floor=5, target_pre_fb=180,
            face_brightness_target_min=230, face_brightness_target_max=245,
            white_ceiling=250, highlight_start=200, dither_method="none",
            export_mode="8bit", step_mm=0.300, dither_method_1bit="jarvis"))
        laser_80w: MachineConfig = Field(default_factory=lambda: MachineConfig(
            glow_size_min=15, glow_size_max=25, glow_opacity_min=10, glow_opacity_max=20,
            glow_style="outer", stone_gamma=1.0, unsharp_threshold=3, shadow_floor=5, target_pre_fb=150,
            face_brightness_target_min=160, face_brightness_target_max=180,
            white_ceiling=235, highlight_start=195, dither_method="none",
            export_mode="8bit", step_mm=0.250, dither_method_1bit="jarvis"))
        impact: MachineConfig = Field(default_factory=lambda: MachineConfig(
            glow_size_min=10, glow_size_max=25, glow_opacity_min=60, glow_opacity_max=80,
            glow_style="outer", stone_gamma=0.90, unsharp_threshold=2, target_pre_fb=160,
            face_brightness_target_min=200, face_brightness_target_max=225,
            white_ceiling=240, highlight_start=200,
            shadow_noise_min=5, shadow_noise_max=15, shadow_floor=8, dither_method="none",
            export_mode="8bit", step_mm=0.300, dither_method_1bit="stucki"))

    class MachineGlobalConfig(BaseModel):
        step_mm: float = Field(0.300, ge=0.10, le=0.50)

    class StoneConfig(BaseModel):
        type: str = Field("granite", deprecated=True, description="Deprecated: use 'material'")
        material: str = Field("granite", pattern="^(granite|marble|gabbro|basalt|acrylic)$")
        heterogeneity: float | None = Field(None, ge=0.0, le=10.0)

        @model_validator(mode="after")
        def sync_type_and_material(self):
            """Синхронизировать type и material (material — источник истины)."""
            if self.material:
                self.type = self.material
            elif self.type:
                self.material = self.type
            return self

    class VignetteConfig(BaseModel):
        vertical_offset: float = Field(0.10, ge=0.0, le=0.3)
        vertical_diameter: float = Field(0.50, ge=0.2, le=0.8)
        blur_radius: int = Field(60, ge=10, le=120)
        headroom: float = Field(0.6, ge=0.2, le=1.0)
        horizontal_oversize: float = Field(0.2, ge=0.0, le=0.5)

    class RetouchConfig(BaseModel):
        config_version: int = Field(CONFIG_VERSION, ge=1)
        processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
        machine: MachineGlobalConfig = Field(default_factory=MachineGlobalConfig)
        stone: StoneConfig = Field(default_factory=StoneConfig)
        vignette: VignetteConfig = Field(default_factory=VignetteConfig)
        model_config = {"extra": "allow"}

    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


def deep_merge(base: dict, override: dict) -> dict:
    """Рекурсивно сливает override в base. override побеждает.
    base копируется глубоко (deepcopy) — мутация результата не затрагивает оригинал."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def find_config_path() -> Path | None:
    """Найти config.yaml. Единая точка поиска для CLI и backend."""
    candidates = [
        Path(__file__).parent.parent / "config.yaml",
        Path.cwd() / "config.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _migrate_face_target(config: dict) -> dict:
    """Конвертировать face_brightness_target: [min, max] → отдельные ключи _min/_max.

    Старый формат (список) использовался до v3.1. Новый формат — два отдельных
    ключа для совместимости с UI-слайдерами. Вызывается автоматически в load_config().
    Также мигрирует старый ключ 'laser' → 'laser_standard'.
    Также мигрирует 'brightness' → 'stone_gamma' (FIX #1/#8).
    """
    proc = config.get("processing", {})

    # Миграция: laser → laser_standard
    if "laser" in proc and "laser_standard" not in proc:
        proc["laser_standard"] = proc.pop("laser")

    for machine in MACHINE_TYPES:
        mc = proc.get(machine, {})
        if "face_brightness_target" in mc and isinstance(mc["face_brightness_target"], list):
            target = mc.pop("face_brightness_target")
            if len(target) >= 2:
                mc["face_brightness_target_min"] = target[0]
                mc["face_brightness_target_max"] = target[1]

        # FIX #1/#8: миграция brightness → stone_gamma
        # brightness > 1.0 осветлял → stone_gamma = 1/brightness < 1.0 (тоже осветляет)
        # brightness < 1.0 затемнял → stone_gamma = 1/brightness > 1.0 (тоже затемняет)
        if "brightness" in mc and "stone_gamma" not in mc:
            old_brightness = mc.pop("brightness")
            if old_brightness != 1.0:
                new_gamma = round(1.0 / max(old_brightness, 0.01), 2)
                logger.warning(
                    "processing.%s: 'brightness=%.2f' мигрирован в 'stone_gamma=%.2f'. "
                    "Семантика: stone_gamma < 1.0 осветляет, > 1.0 затемняет. "
                    "Проверьте результат гравировки.",
                    machine, old_brightness, new_gamma,
                )
                mc["stone_gamma"] = new_gamma
            else:
                mc["stone_gamma"] = 1.0
        elif "brightness" in mc:
            mc.pop("brightness")  # stone_gamma уже есть — просто удаляем brightness

    return config


# ---------------------------------------------------------------------------
# Цепочка миграций (config_version → config_version + 1)
# ---------------------------------------------------------------------------


def _migrate_v0_to_v1(config: dict) -> dict:
    """Миграция v0 → v1: face_brightness_target list → min/max,
    laser → laser_standard, brightness → stone_gamma."""
    return _migrate_face_target(config)


def _migrate_v1_to_v2(config: dict) -> dict:
    """Миграция v1 → v2: добавление config_version, ничего не меняет
    в существующих ключах — версияфикация конфига."""
    config["config_version"] = 2
    return config


def _migrate_v2_to_v3(config: dict) -> dict:
    """Миграция v2 → v3: dither_method → export_mode, global step_mm → per-machine, laser_80w gamma/fb.

    Изменения:
    - dither_method="none" → export_mode="8bit"
    - dither_method="jarvis"/"stucki" → export_mode="1bit", dither_method_1bit сохраняется
    - Глобальный machine.step_mm копируется в per-machine (если не задан)
    - laser_80w: stone_gamma 0.85→1.0, face_brightness перекалибровка
    """
    proc = config.get("processing", {})

    for machine in MACHINE_TYPES:
        mc = proc.get(machine, {})

        # dither_method → export_mode
        if "export_mode" not in mc and "dither_method" in mc:
            dm = mc.pop("dither_method")
            if dm in ("none",):
                mc["export_mode"] = "8bit"
            else:
                mc["export_mode"] = "1bit"
                mc["dither_method_1bit"] = dm  # сохранить для 1bit режима

        # Per-machine step_mm из глобального (если не задан)
        if "step_mm" not in mc:
            mc["step_mm"] = config.get("machine", {}).get("step_mm", 0.300)

        # dither_method_1bit по умолчанию — если не задан
        if "dither_method_1bit" not in mc:
            mc["dither_method_1bit"] = "jarvis" if machine != "impact" else "stucki"

    # laser_80w: stone_gamma 0.85→1.0 + face_brightness recalibration
    mc_80w = proc.get("laser_80w", {})
    if mc_80w.get("stone_gamma") == 0.85:
        mc_80w["stone_gamma"] = 1.0
    if mc_80w.get("face_brightness_target_min") == 190:
        mc_80w["face_brightness_target_min"] = 160
    if mc_80w.get("face_brightness_target_max") == 210:
        mc_80w["face_brightness_target_max"] = 180

    config["config_version"] = 3
    return config


def _migrate_v3_to_v4(config: dict) -> dict:
    """Миграция v3 → v4: stone.type → material (alias, оба ключа записываются).

    Добавляет 'material' как alias для 'stone.type' с deprecation warning.
    Оба ключа синхронизируются — material является источником истины.
    """
    stone = config.get("stone", {})
    if "type" in stone and "material" not in stone:
        stone["material"] = stone["type"]
        logger.warning(
            "config: 'stone.type' is deprecated, use 'material' instead. "
            "Auto-migrating for this session."
        )
    elif "material" in stone and "type" not in stone:
        stone["type"] = stone["material"]  # backward compat для пайплайна
    elif "material" in stone and "type" in stone:
        # Оба указаны — material имеет приоритет
        if stone["material"] != stone["type"]:
            logger.warning(
                "config: both 'stone.type' and 'material' specified with different values. "
                "Using 'material' (%s), ignoring 'stone.type' (%s).",
                stone["material"], stone["type"]
            )
        stone["type"] = stone["material"]

    config["config_version"] = 4
    return config


# Реестр миграций: version → функция миграции до version+1
_MIGRATIONS = {
    0: _migrate_v0_to_v1,
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
    3: _migrate_v3_to_v4,
}


def _run_migrations(config: dict) -> dict:
    """Запустить все миграции последовательно.

    Миграции выполняются ВСЕГДА, независимо от config_version в конфиге,
    потому что deep_merge(DEFAULTS, yaml) может добавить config_version
    из DEFAULTS раньше, чем YAML-ключи будут мигрированы.
    Все миграции идемпотентны — повторный запуск безопасен.
    """
    for version in sorted(_MIGRATIONS.keys()):
        config = _MIGRATIONS[version](config)
    config["config_version"] = CONFIG_VERSION
    return config


def _sync_stone_type_material(config: dict) -> dict:
    """Синхронизировать stone.type и stone.material в загруженном конфиге.

    После deep_merge с DEFAULTS (v4) оба ключа присутствуют.
    Если YAML содержал только stone.type — миграция v3→v4 уже добавила material.
    Если YAML содержал только material — добавляем type для backward compat.
    """
    stone = config.get("stone", {})
    if "material" in stone and "type" in stone:
        # Оба есть — material имеет приоритет, синхронизируем type
        stone["type"] = stone["material"]
    elif "type" in stone and "material" not in stone:
        # Только type — добавляем material (миграция уже должна была отработать,
        # но на всякий случай проверяем ещё раз)
        stone["material"] = stone["type"]
    elif "material" in stone and "type" not in stone:
        # Только material — добавляем type для backward compat пайплайна
        stone["type"] = stone["material"]
    return config


def load_config(config_path=None):
    """Загрузить конфиг: YAML с deep-merge поверх DEFAULTS.
    DEFAULTS копируется глубоко — мутация результата не мутирует DEFAULTS.
    Поддерживает оба ключа: stone.type и stone.material (v4).
    Поиск config_path делегирован find_config_path()."""
    if config_path is None:
        config_path = find_config_path()

    if config_path and Path(config_path).exists():
        if not HAS_YAML:
            logger.warning(
                "PyYAML not installed, ignoring %s. Install: uv pip install PyYAML",
                config_path,
            )
            return copy.deepcopy(DEFAULTS)
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}
        # Миграции запускаются ДО deep_merge с DEFAULTS,
        # иначе DEFAULTS["stone"]["material"] = "granite" затирает
        # пользовательский stone.type из v3-конфига (AUDIT-7).
        yaml_config = _run_migrations(yaml_config)
        yaml_config = _sync_stone_type_material(yaml_config)
        merged = deep_merge(DEFAULTS, yaml_config)
        merged = _sync_stone_type_material(merged)
        return merged

    # Нет config.yaml — вернуть глубокую копию DEFAULTS.
    # deepcopy гарантирует, что мутация результата не затронет глобальный DEFAULTS.
    return copy.deepcopy(DEFAULTS)


def save_config(config_path: Path, config: dict) -> None:
    """Сохранить конфиг, записав оба ключа (material + stone.type) для совместимости."""
    stone = config.get("stone", {})
    if "material" in stone:
        stone["type"] = stone["material"]  # backward compat
    elif "type" in stone:
        stone["material"] = stone["type"]  # forward compat

    if not HAS_YAML:
        raise RuntimeError("PyYAML not installed, cannot save config")

    config_path.write_text(
        yaml.dump(config, allow_unicode=True, default_flow_style=False),
        encoding="utf-8"
    )


def validate_config(config: dict) -> list[str]:
    """Валидация конфига. Возвращает список предупреждений.
    Использует Pydantic если доступен, иначе — dict-проверки."""
    warnings = []

    if HAS_PYDANTIC:
        try:
            from pydantic import ValidationError as PydanticValidationError
            RetouchConfig(**config)
        except PydanticValidationError as e:
            warnings.append(f"Config validation: {e}")

    # Кросс-валидация (Pydantic не проверяет отношения полей)
    for machine in MACHINE_TYPES:
        mc = config.get("processing", {}).get(machine, {})
        if mc.get("glow_size_min", 0) > mc.get("glow_size_max", 0):
            warnings.append(f"processing.{machine}: glow_size_min > glow_size_max")
        if mc.get("glow_opacity_min", 0) > mc.get("glow_opacity_max", 0):
            warnings.append(f"processing.{machine}: glow_opacity_min > glow_opacity_max")
        if mc.get("face_brightness_target_min", 0) > mc.get("face_brightness_target_max", 0):
            warnings.append(f"processing.{machine}: face_brightness_target_min > face_brightness_target_max")

    return warnings
