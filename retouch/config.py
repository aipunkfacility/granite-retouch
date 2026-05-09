"""Загрузка и валидация конфигурации из config.yaml."""

import copy
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


# Все допустимые значения machine_type
MACHINE_TYPES = ("laser_standard", "laser_80w", "impact")

# Профили камней (B.2: stone_type → heterogeneity)
STONE_PROFILES = {
    "granite": {"heterogeneity": 2.0},
    "gabbro": {"heterogeneity": 1.0},
    "basalt": {"heterogeneity": 1.5},
    "marble": {"heterogeneity": 3.0},
}

DEFAULTS = {
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
            "dither_method": "none",  # FIX #9: 8-bit BMP, без дизеринга
        },
        "laser_80w": {
            "glow_size_min": 15, "glow_size_max": 25,
            "glow_opacity_min": 10, "glow_opacity_max": 20,
            "glow_style": "outer",
            "stone_gamma": 0.85,  # FIX #8: SOP 5.1
            "unsharp_threshold": 3,  # FIX #11: SOP 3.1
            "shadow_floor": 5,  # FIX #12: SOP 5.1
            "target_pre_fb": 150,
            "face_brightness_target_min": 190,
            "face_brightness_target_max": 210,
            "white_ceiling": 235,
            "face_region_top": 0.45,
            "highlight_start": 160,
            "dither_method": "jarvis",  # FIX #9: SOP 4.1
            "dither_upsample": 2,  # FIX #10: SOP 5.2
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
            "highlight_start": 160,
            "shadow_noise_min": 5,
            "shadow_noise_max": 15,
            "shadow_noise_threshold": 30,  # A.1: порог для shadow noise
            "shadow_floor": 8,  # A.2: минимальная яркость для impact
            "dither_method": "stucki",  # FIX #9: SOP 4.1
        },
    },
    "machine": {
        "step_mm": 0.300,  # B.2: шаг ЧПУ для расчёта BMP resolution
    },
    "stone": {
        "type": "granite",  # B.2: тип камня
        "heterogeneity": None,  # None = auto по stone_type → STONE_PROFILES
    },
    "vignette": {
        "vertical_offset": 0.10,  # FIX #3: восстановлено (было 0.30)
        "vertical_diameter": 0.55,
        "blur_radius": 60,
        "headroom": 0.6,
        "horizontal_oversize": 0.2,
    },
}


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


# --- Pydantic модели (optional) ---

if HAS_PYDANTIC:
    class MachineConfig(BaseModel):
        glow_size_min: int = Field(40, ge=5, le=100)
        glow_size_max: int = Field(80, ge=5, le=100)
        glow_opacity_min: int = Field(30, ge=10, le=100)
        glow_opacity_max: int = Field(40, ge=10, le=100)
        glow_style: str = Field("outer", pattern="^(inner|outer)$")
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
        dither_method: str = Field("none", pattern="^(none|floyd_steinberg|jarvis|stucki)$")  # FIX #9
        dither_upsample: int = Field(1, ge=1, le=4)  # FIX #10
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
            white_ceiling=250, highlight_start=200, dither_method="none"))
        laser_80w: MachineConfig = Field(default_factory=lambda: MachineConfig(
            glow_size_min=15, glow_size_max=25, glow_opacity_min=10, glow_opacity_max=20,
            glow_style="outer", stone_gamma=0.85, unsharp_threshold=3, shadow_floor=5, target_pre_fb=150,
            face_brightness_target_min=190, face_brightness_target_max=210,
            white_ceiling=235, highlight_start=160, dither_method="jarvis", dither_upsample=2))
        impact: MachineConfig = Field(default_factory=lambda: MachineConfig(
            glow_size_min=10, glow_size_max=25, glow_opacity_min=60, glow_opacity_max=80,
            glow_style="outer", stone_gamma=0.90, unsharp_threshold=2, target_pre_fb=160,
            face_brightness_target_min=200, face_brightness_target_max=225,
            white_ceiling=240, highlight_start=160,
            shadow_noise_min=5, shadow_noise_max=15, shadow_floor=8, dither_method="stucki"))

    class MachineGlobalConfig(BaseModel):
        step_mm: float = Field(0.300, ge=0.10, le=0.50)

    class StoneConfig(BaseModel):
        type: str = Field("granite", pattern="^(granite|marble|gabbro|basalt)$")
        heterogeneity: float | None = Field(None, ge=0.0, le=10.0)

    class VignetteConfig(BaseModel):
        vertical_offset: float = Field(0.10, ge=0.0, le=0.3)
        vertical_diameter: float = Field(0.50, ge=0.2, le=0.8)
        blur_radius: int = Field(60, ge=10, le=120)
        headroom: float = Field(0.6, ge=0.2, le=1.0)
        horizontal_oversize: float = Field(0.2, ge=0.0, le=0.5)

    class RetouchConfig(BaseModel):
        processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
        machine: MachineGlobalConfig = Field(default_factory=MachineGlobalConfig)
        stone: StoneConfig = Field(default_factory=StoneConfig)
        vignette: VignetteConfig = Field(default_factory=VignetteConfig)
        model_config = {"extra": "allow"}


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
        if "brightness" in mc and "stone_gamma" not in mc:
            import logging
            old_brightness = mc.pop("brightness")
            # brightness < 1.0 → stone_gamma = brightness (тот же числовой диапазон,
            # но другая семантика: gamma < 1 осветляет тени, brightness < 1 затемнял)
            # Предупреждаем о смене семантики
            if old_brightness != 1.0:
                logging.getLogger(__name__).warning(
                    "processing.%s: 'brightness=%.2f' мигрирован в 'stone_gamma=%.2f'. "
                    "Семантика изменилась: stone_gamma < 1.0 ОСВЕТЛЯЕТ тени "
                    "(вместо затемнения brightness). Проверьте результат.",
                    machine, old_brightness, old_brightness,
                )
            mc["stone_gamma"] = old_brightness
        elif "brightness" in mc:
            mc.pop("brightness")  # stone_gamma уже есть — просто удаляем brightness

    return config


def load_config(config_path=None):
    """Загрузить конфиг: YAML с deep-merge поверх DEFAULTS.
    DEFAULTS копируется глубоко — мутация результата не мутирует DEFAULTS.
    Поиск config_path делегирован find_config_path()."""
    defaults = copy.deepcopy(DEFAULTS)

    if config_path is None:
        config_path = find_config_path()

    if config_path and Path(config_path).exists():
        if not HAS_YAML:
            import logging
            logging.getLogger(__name__).warning(
                "PyYAML not installed, ignoring %s. Install: uv pip install PyYAML",
                config_path,
            )
            return defaults
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}
        merged = deep_merge(defaults, yaml_config)
        return _migrate_face_target(merged)

    return defaults


def validate_config(config: dict) -> list[str]:
    """Валидация конфига. Возвращает список предупреждений.
    Использует Pydantic если доступен, иначе — dict-проверки."""
    warnings = []

    if HAS_PYDANTIC:
        try:
            RetouchConfig(**config)
        except Exception as e:
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
