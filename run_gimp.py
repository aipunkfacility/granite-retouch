#!/usr/bin/env python3
"""Запуск GIMP-постобработки через CLI.

Находит GIMP по стандартным путям или env var GIMP_PATH,
генерирует временный Script-Fu с правильными параметрами
и запускает GIMP в headless-режиме.
"""

import argparse
import os
import subprocess
import sys
import tempfile


GIMP_SEARCH_PATHS = [
    os.environ.get("GIMP_PATH", ""),
    r"F:\GIMP 2\bin\gimp-console-2.10.exe",
    r"C:\Program Files\GIMP 2\bin\gimp-console-2.10.exe",
]

SCM_TEMPLATE = """(begin
  (load "{scm_path}")
  (retouch-process-order "{input_path}" "{output_path}" "{machine_type}")
)
"""


def find_gimp():
    """Найти исполняемый файл GIMP по стандартным путям."""
    for path in GIMP_SEARCH_PATHS:
        if path and os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "GIMP не найден. Задайте переменную окружения GIMP_PATH "
        "или добавьте путь в GIMP_SEARCH_PATHS в run_gimp.py"
    )


def find_scm_script():
    """Найти retouch_process.scm рядом с этим скриптом."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scm_path = os.path.join(script_dir, "retouch_process.scm")
    if not os.path.isfile(scm_path):
        raise FileNotFoundError(
            f"Script-Fu не найден: {scm_path}"
        )
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
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        parser.error(f"Входной файл не найден: {args.input}")

    gimp_exe = find_gimp()
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
