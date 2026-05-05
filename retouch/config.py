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


DEFAULTS = {
    "processing": {
        "blue_threshold": 30,
        "min_blue_ratio": 0.15,
        "min_resolution": 512,
        "result_min_black_ratio": 0.25,
        "fringe_radius": 3,
        "laser": {
            "glow_size_min": 40, "glow_size_max": 80,
            "glow_opacity_min": 30, "glow_opacity_max": 40,
            "brightness": 1.18,
            "face_brightness_target": [230, 245],
            "face_region_top": 0.45,
            "highlight_start": 200,
        },
        "impact": {
            "glow_size_min": 10, "glow_size_max": 25,
            "glow_opacity_min": 60, "glow_opacity_max": 80,
            "brightness": 1.00,
            "face_brightness_target": [185, 210],
            "face_region_top": 0.45,
            "highlight_start": 200,
        },
    },
    "vignette": {
        "vertical_offset": 0.10,
        "vertical_diameter": 0.50,
        "blur_radius": 60,
        "headroom": 0.6,
        "horizontal_oversize": 0.2,
    },
}


# --- Pydantic модели (optional) ---

if HAS_PYDANTIC:
    class MachineConfig(BaseModel):
        glow_size_min: int = Field(40, ge=5, le=100)
        glow_size_max: int = Field(80, ge=5, le=100)
        glow_opacity_min: int = Field(30, ge=10, le=100)
        glow_opacity_max: int = Field(40, ge=10, le=100)
        brightness: float = Field(1.18, ge=0.5, le=1.5)
        face_brightness_target: list[int] = Field([230, 245])
        face_region_top: float = Field(0.45, ge=0.2, le=0.8)
        highlight_start: int = Field(200, ge=100, le=250)

    class ProcessingConfig(BaseModel):
        blue_threshold: int = Field(30, ge=10, le=80)
        min_blue_ratio: float = Field(0.15, ge=0.0, le=1.0)
        fringe_radius: int = Field(3, ge=0, le=10)
        laser: MachineConfig = Field(default_factory=lambda: MachineConfig(
            glow_size_min=40, glow_size_max=80, glow_opacity_min=30, glow_opacity_max=40,
            brightness=1.18, face_brightness_target=[230, 245]))
        impact: MachineConfig = Field(default_factory=lambda: MachineConfig(
            glow_size_min=10, glow_size_max=25, glow_opacity_min=60, glow_opacity_max=80,
            brightness=1.00, face_brightness_target=[185, 210]))

    class VignetteConfig(BaseModel):
        vertical_offset: float = Field(0.10, ge=0.0, le=0.3)
        vertical_diameter: float = Field(0.50, ge=0.2, le=0.8)
        blur_radius: int = Field(60, ge=10, le=120)
        headroom: float = Field(0.6, ge=0.2, le=1.0)
        horizontal_oversize: float = Field(0.2, ge=0.0, le=0.5)

    class RetouchConfig(BaseModel):
        processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
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
        return deep_merge(defaults, yaml_config)

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
    for machine in ("laser", "impact"):
        mc = config.get("processing", {}).get(machine, {})
        if mc.get("glow_size_min", 0) > mc.get("glow_size_max", 0):
            warnings.append(f"processing.{machine}: glow_size_min > glow_size_max")
        if mc.get("glow_opacity_min", 0) > mc.get("glow_opacity_max", 0):
            warnings.append(f"processing.{machine}: glow_opacity_min > glow_opacity_max")

    return warnings
