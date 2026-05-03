"""Загрузка конфигурации из config.yaml."""

from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


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
            "brightness": 1.05,
            "face_brightness_target": [230, 245],
        },
        "impact": {
            "glow_size_min": 10, "glow_size_max": 25,
            "glow_opacity_min": 60, "glow_opacity_max": 80,
            "brightness": 1.00,
            "face_brightness_target": [185, 210],
            "shadow_noise": True,
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


def load_config(config_path=None):
    """Загрузить конфигурацию из config.yaml. Fallback на DEFAULTS.

    Args:
        config_path: явный путь к config.yaml, или None для автопоиска

    Returns:
        dict: конфигурация
    """
    if config_path is None:
        script_dir = Path(__file__).resolve().parent.parent  # retouch/ → project root
        candidates = [
            script_dir / "config.yaml",
            Path.cwd() / "config.yaml",
        ]
        for candidate in candidates:
            if candidate.is_file():
                config_path = candidate
                break

    if config_path and Path(config_path).is_file():
        if not HAS_YAML:
            print(f"Warning: PyYAML not installed, ignoring {config_path}. "
                  f"Install: uv pip install PyYAML")
            return DEFAULTS
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        print(f"Config loaded: {config_path}")
        return config

    return DEFAULTS
