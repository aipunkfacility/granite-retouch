"""Поиск и запуск GIMP для постобработки."""

import os
import subprocess
import sys
from pathlib import Path

from retouch.config import DEFAULTS, load_config

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

GIMP_FALLBACK_PATHS = [
    r"F:\GIMP 2\bin\gimp-console-2.10.exe",
    r"C:\Program Files\GIMP 2\bin\gimp-console-2.10.exe",
]

VIGNETTE_DEFAULTS = {
    "vertical_offset": 0.10,
    "vertical_diameter": 0.50,
    "blur_radius": 60,
    "headroom": 0.6,
    "horizontal_oversize": 0.2,
}

SCM_TEMPLATE = """(begin
  (load "{scm_path}")
  (retouch-process-order "{input_path}" "{output_path}" "{machine_type}"
    {v_offset} {v_diameter} {headroom} {h_oversize} {blur_radius})
)
"""


def get_vignette_params(config):
    """Извлечь параметры виньетки из конфига."""
    if config and "vignette" in config:
        vign = config["vignette"]
        return {k: vign.get(k, v) for k, v in VIGNETTE_DEFAULTS.items()}
    return dict(VIGNETTE_DEFAULTS)


def find_gimp(gimp_config=None):
    """Найти исполняемый файл GIMP.

    Приоритет: env var → config.yaml → fallback paths.
    """
    env_var_name = "GIMP_PATH"
    if gimp_config:
        env_var_name = gimp_config.get("env_var", "GIMP_PATH")

    env_path = os.environ.get(env_var_name, "")
    if env_path and os.path.isfile(env_path):
        return env_path

    if gimp_config and "search_paths" in gimp_config:
        for path in gimp_config["search_paths"]:
            if path and os.path.isfile(path):
                return path

    for path in GIMP_FALLBACK_PATHS:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        f"GIMP не найден. Задайте {env_var_name} env var, "
        f"укажите gimp.search_paths в config.yaml, "
        f"или добавьте путь в GIMP_FALLBACK_PATHS"
    )


def find_scm_script():
    """Найти retouch_process.scm в корне проекта."""
    script_dir = Path(__file__).resolve().parent.parent.parent  # retouch/gimp/runner.py → project root
    scm_path = script_dir / "retouch_process.scm"
    if not scm_path.is_file():
        raise FileNotFoundError(f"Script-Fu не найден: {scm_path}")
    return str(scm_path)


def run_gimp(input_path, output_path, machine_type="laser", config=None):
    """Запустить GIMP-постобработку.

    Args:
        input_path: путь к входному изображению
        output_path: путь к выходному файлу
        machine_type: тип станка (laser/impact)
        config: конфигурация (default: auto-load)

    Returns:
        int: exit code GIMP (0 = успех)
    """
    if config is None:
        config = load_config()

    gimp_config = config.get("gimp") if config else None
    vignette = get_vignette_params(config)

    gimp_exe = find_gimp(gimp_config)
    scm_path = find_scm_script()

    # Escape for Scheme (strip paths to remove possible trailing newlines)
    scm_escaped = scm_path.replace("\\", "\\\\").strip()
    input_escaped = os.path.abspath(input_path).replace("\\", "\\\\").strip()
    output_escaped = os.path.abspath(output_path).replace("\\", "\\\\").strip()

    scm_command = SCM_TEMPLATE.format(
        scm_path=scm_escaped,
        input_path=input_escaped,
        output_path=output_escaped,
        machine_type=machine_type,
        v_offset=vignette["vertical_offset"],
        v_diameter=vignette["vertical_diameter"],
        headroom=vignette["headroom"],
        h_oversize=vignette["horizontal_oversize"],
        blur_radius=int(vignette["blur_radius"]),
    )

    cmd = [gimp_exe, "-i", "-b", scm_command, "-b", "(gimp-quit 0)"]

    print(f"Running GIMP: {gimp_exe}")
    print(f"Machine type: {machine_type}")
    print(f"Vignette: offset={vignette['vertical_offset']}, "
          f"diameter={vignette['vertical_diameter']}, "
          f"headroom={vignette['headroom']}, "
          f"oversize={vignette['horizontal_oversize']}, "
          f"blur={vignette['blur_radius']}")
    print(f"Scheme command:\n{scm_command}")

    # GIMP на русской Windows пишет в UTF-8, а system default — CP1251.
    # Используем bytes + decode с errors='replace' чтобы избежать UnicodeDecodeError.
    result = subprocess.run(cmd, capture_output=True)
    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")

    if stdout.strip():
        print(f"GIMP stdout:\n{stdout.strip()}")
    if stderr.strip():
        print(f"GIMP stderr:\n{stderr.strip()}", file=sys.stderr)

    return result.returncode
