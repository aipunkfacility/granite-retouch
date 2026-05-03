#!/usr/bin/env python3
"""Запуск GIMP-постобработки через CLI.

Находит GIMP по config.yaml, env var GIMP_PATH или стандартным путям,
генерирует Script-Fu с правильными параметрами
и запускает GIMP в headless-режиме.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Fallback search paths when config.yaml is unavailable
GIMP_FALLBACK_PATHS = [
    r"F:\GIMP 2\bin\gimp-console-2.10.exe",
    r"C:\Program Files\GIMP 2\bin\gimp-console-2.10.exe",
]

SCM_TEMPLATE = """(begin
  (load "{scm_path}")
  (retouch-process-order "{input_path}" "{output_path}" "{machine_type}")
)
"""


def load_gimp_config(config_path=None):
    """Загрузить секцию gimp из config.yaml."""
    if config_path is None:
        script_dir = Path(__file__).parent
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
            return None
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("gimp")

    return None


def find_gimp(gimp_config=None):
    """Найти исполняемый файл GIMP.

    Приоритет:
    1. env var GIMP_PATH
    2. config.yaml → gimp.search_paths
    3. Fallback GIMP_FALLBACK_PATHS
    """
    # 1. Environment variable (highest priority)
    env_var_name = "GIMP_PATH"
    if gimp_config:
        env_var_name = gimp_config.get("env_var", "GIMP_PATH")

    env_path = os.environ.get(env_var_name, "")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. config.yaml search_paths
    if gimp_config and "search_paths" in gimp_config:
        for path in gimp_config["search_paths"]:
            if path and os.path.isfile(path):
                return path

    # 3. Fallback
    for path in GIMP_FALLBACK_PATHS:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        f"GIMP не найден. Задайте {env_var_name} env var, "
        f"укажите gimp.search_paths в config.yaml, "
        f"или добавьте путь в GIMP_FALLBACK_PATHS в run_gimp.py"
    )


def find_scm_script():
    """Найти retouch_process.scm рядом с этим скриптом."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scm_path = os.path.join(script_dir, "retouch_process.scm")
    if not os.path.isfile(scm_path):
        raise FileNotFoundError(f"Script-Fu не найден: {scm_path}")
    return scm_path


def main():
    parser = argparse.ArgumentParser(
        description="granite-retouch — запуск GIMP-постобработки"
    )
    parser.add_argument("--input", "-i", required=True,
        help="Путь к входному изображению (PNG с синим хромакеем)")
    parser.add_argument("--output", "-o", required=True,
        help="Путь к выходному файлу (TIFF)")
    parser.add_argument("--machine", "-m",
        choices=["laser", "impact"], default="laser",
        help="Тип станка гравировки (default: laser)")
    parser.add_argument("--config", "-c",
        help="Путь к config.yaml (default: auto-detect)")
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        parser.error(f"Входной файл не найден: {args.input}")

    gimp_config = load_gimp_config(args.config)
    gimp_exe = find_gimp(gimp_config)
    scm_path = find_scm_script()

    # Escape backslashes for Scheme strings (Windows paths)
    scm_escaped = scm_path.replace("\\", "\\\\")
    input_escaped = os.path.abspath(args.input).replace("\\", "\\\\")
    output_escaped = os.path.abspath(args.output).replace("\\", "\\\\")

    # Build Script-Fu command
    scm_command = SCM_TEMPLATE.format(
        scm_path=scm_escaped,
        input_path=input_escaped,
        output_path=output_escaped,
        machine_type=args.machine,
    )

    # GIMP batch command
    cmd = [
        gimp_exe, "-i",
        "-b", scm_command,
        "-b", "(gimp-quit 0)",
    ]

    print(f"Running GIMP: {gimp_exe}")
    print(f"Machine type: {args.machine}")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"GIMP error: {result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)

    print("GIMP processing complete.")


if __name__ == "__main__":
    main()
