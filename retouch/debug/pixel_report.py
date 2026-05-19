"""Попиксельный анализ портрета БЕЗ масок — по яркостным зонам.

Использование:
  from retouch.debug.pixel_report import PixelReport
  r = PixelReport(source_path="source.png", output_path="out.bmp", machine_type="impact")
  r.run()
  print(r.summary_text())
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from retouch.config import DEFAULTS

logger = logging.getLogger(__name__)

# ─── Зоны яркости ─────────────────────────────────────────────────────────

ZONE_DARK = (0, 50)       # одежда
ZONE_MID = (50, 150)      # волосы, тени
ZONE_BRIGHT = (150, 220)  # лицо
ZONE_HOT = (220, 256)     # воротник, блики


def _zone_mask(arr: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Булева маска пикселей в диапазоне [lo, hi)."""
    return (arr >= lo) & (arr < hi)


def _zone_name(lo: int, hi: int) -> str:
    names = {
        ZONE_DARK: "тёмная (одежда)",
        ZONE_MID: "средняя (волосы)",
        ZONE_BRIGHT: "яркая (лицо)",
        ZONE_HOT: "очень яркая (воротник)",
    }
    return names.get((lo, hi), f"{lo}-{hi}")


# ─── Dataclasses ──────────────────────────────────────────────────────────

@dataclass
class ZoneStats:
    """Статистика одной яркостной зоны."""
    name: str = ""
    lo: int = 0
    hi: int = 0
    count: int = 0
    pct_of_total: float = 0.0
    median: float = 0.0
    mean: float = 0.0
    p90: float = 0.0
    p95: float = 0.0
    p98: float = 0.0
    max_val: float = 0.0
    variance: float = 0.0
    plateau_pct: float = 0.0
    plateau_peak: int = 0
    plateau_max_run: int = 0
    n_unique: int = 0


@dataclass
class PixelReport:
    source_path: str = ""
    output_path: str = ""
    machine_type: str = "laser_standard"
    white_ceiling: int = 250

    source_zones: dict = field(default_factory=dict)
    output_zones: dict = field(default_factory=dict)
    source_arr: Optional[np.ndarray] = None
    output_arr: Optional[np.ndarray] = None

    def __post_init__(self):
        if not self.machine_type:
            self.machine_type = "laser_standard"
        mc = DEFAULTS.get("processing", {}).get(self.machine_type, {})
        self.white_ceiling = int(mc.get("white_ceiling", 250))

    def run(self):
        self.source_arr = self._load_gray(self.source_path)
        self.output_arr = self._load_gray(self.output_path)
        if self.source_arr is None or self.output_arr is None:
            raise ValueError("source или output не загрузились")

        # Ресайз source под output если нужно
        if self.source_arr.shape[:2] != self.output_arr.shape[:2]:
            h, w = self.output_arr.shape[:2]
            self.source_arr = np.array(
                Image.fromarray(self.source_arr).resize((w, h), Image.LANCZOS)
            )

        for lo, hi in [ZONE_DARK, ZONE_MID, ZONE_BRIGHT, ZONE_HOT]:
            self.source_zones[(lo, hi)] = self._analyze_zone(
                self.source_arr, lo, hi, "source"
            )
            self.output_zones[(lo, hi)] = self._analyze_zone(
                self.output_arr, lo, hi, "output"
            )

    @staticmethod
    def _load_gray(path: str) -> Optional[np.ndarray]:
        if not path or not os.path.isfile(path):
            logger.warning("Файл не найден: %s", path)
            return None
        img = Image.open(path).convert("L")
        return np.array(img, dtype=np.uint8)

    def _analyze_zone(self, arr: np.ndarray, lo: int, hi: int,
                      tag: str) -> ZoneStats:
        mask = _zone_mask(arr, lo, hi)
        pixels = arr[mask]
        total = arr.size
        count = int(mask.sum())
        pct = count / max(total, 1) * 100

        if count == 0:
            return ZoneStats(
                name=_zone_name(lo, hi), lo=lo, hi=hi, count=0,
                pct_of_total=pct,
            )

        p90, p95, p98 = np.percentile(pixels, [90, 95, 98])

        # Плато: сканируем строки, ищем run'ы >= 5 px с tolerance=2
        plateau_map = np.zeros(arr.shape[:2], dtype=bool)
        for y in range(arr.shape[0]):
            row = arr[y, :].astype(int)
            i = 0
            while i < arr.shape[1]:
                j = i
                while j < arr.shape[1] and abs(int(row[j]) - int(row[i])) <= 2:
                    j += 1
                if j - i >= 5:
                    plateau_map[y, i:j] = True
                i = j

        zone_plateau = plateau_map[mask]
        plateau_count = int(zone_plateau.sum())
        plateau_pct = plateau_count / max(count, 1) * 100

        # Peak plateau value
        plateau_peak = 0
        plateau_max_run = 0
        if plateau_count > 0:
            plateau_vals = arr[mask][zone_plateau]
            if len(plateau_vals):
                unique, counts = np.unique(plateau_vals, return_counts=True)
                plateau_peak = int(unique[counts.argmax()])
            # Max run
            for y in range(arr.shape[0]):
                row_plateau = plateau_map[y, :].astype(int)
                if row_plateau.sum() == 0:
                    continue
                changes = np.diff(np.concatenate(([0], row_plateau, [0])))
                starts = np.where(changes == 1)[0]
                ends = np.where(changes == -1)[0]
                if len(starts):
                    plateau_max_run = max(plateau_max_run, int((ends - starts).max()))

        return ZoneStats(
            name=_zone_name(lo, hi), lo=lo, hi=hi, count=count,
            pct_of_total=round(pct, 1),
            median=round(float(np.median(pixels)), 1),
            mean=round(float(np.mean(pixels)), 1),
            p90=round(float(p90), 1),
            p95=round(float(p95), 1),
            p98=round(float(p98), 1),
            max_val=round(float(pixels.max()), 1),
            variance=round(float(np.var(pixels)), 1),
            plateau_pct=round(plateau_pct, 1),
            plateau_peak=plateau_peak,
            plateau_max_run=plateau_max_run,
            n_unique=len(np.unique(pixels)),
        )

    def summary_text(self) -> str:
        p = []
        p.append(f"Pixel Report: {Path(self.output_path).name}")
        p.append(f"Станок: {self.machine_type} | ceiling={self.white_ceiling}")
        p.append("")

        # Зоны source
        p.append("ИСХОДНИК (ai.png):")
        for lo, hi in [ZONE_BRIGHT, ZONE_HOT]:
            z = self.source_zones.get((lo, hi))
            if z and z.count > 0:
                p.append(f"  {z.name}: {z.count} px ({z.pct_of_total}%), "
                         f"медиана={z.median}, p95={z.p95}, max={z.max_val}")
        p.append("")

        # Зоны output
        p.append("РЕЗУЛЬТАТ:")
        for lo, hi in [ZONE_BRIGHT, ZONE_HOT]:
            sz = self.source_zones.get((lo, hi))
            oz = self.output_zones.get((lo, hi))
            if oz and oz.count > 0:
                p.append(f"  {oz.name}: {oz.count} px ({oz.pct_of_total}%), "
                         f"медиана={oz.median}, p95={oz.p95}, max={oz.max_val}")
                if sz and sz.count > 0:
                    med_shift = oz.median - sz.median
                    p95_shift = oz.p95 - sz.p95
                    p.append(f"    сдвиг: медиана {sz.median}→{oz.median} ({med_shift:+.0f}), "
                             f"p95 {sz.p95}→{oz.p95} ({p95_shift:+.0f})")
                    # Потеря текстуры
                    if sz.variance > 0:
                        var_loss = (sz.variance - oz.variance) / sz.variance * 100
                        p.append(f"    variance: {sz.variance}→{oz.variance} (↓{var_loss:.0f}%)")
                if oz.plateau_pct > 0:
                    p.append(f"    ⚠ ПЛАТО: {oz.plateau_pct}% зоны, пик={oz.plateau_peak}, "
                             f"макс.run={oz.plateau_max_run}px")
                if oz.n_unique < 30:
                    p.append(f"    ⚠ УНИКУМОВ: {oz.n_unique}/{oz.count} px "
                             f"({oz.count//max(oz.n_unique,1)} px/знач)")
        p.append("")

        # Диагноз
        p.append("=" * 50)
        p.append("")
        problems = self._diagnose()
        if problems:
            for pr in problems:
                p.append(f"• {pr}")
        else:
            p.append("Аномалий нет.")
        return "\n".join(p)

    def _diagnose(self) -> list[str]:
        problems = []
        ceiling = self.white_ceiling

        # Проверяем яркие зоны на плато
        for lo, hi in [ZONE_BRIGHT, ZONE_HOT]:
            oz = self.output_zones.get((lo, hi))
            sz = self.source_zones.get((lo, hi))
            if not oz or oz.count == 0:
                continue

            if oz.plateau_pct > 5:
                zone_label = "лица" if lo == ZONE_BRIGHT[0] else "воротника"
                problems.append(
                    f"Плато в зоне {zone_label}: {oz.plateau_pct}% пикселей "
                    f"на значении {oz.plateau_peak}. "
                    f"Макс. сплошной участок: {oz.plateau_max_run}px. "
                    f"Причина: levels factor пережал p95 ({sz.p95 if sz else '?'}→{oz.p95}) "
                    f"в ceiling={ceiling}, мягкий knee не сгладил."
                )

            # Потеря текстуры
            if sz and sz.variance > 0:
                var_loss = (sz.variance - oz.variance) / sz.variance * 100
                if var_loss > 40:
                    zone_label = "лица" if lo == ZONE_BRIGHT[0] else "воротника"
                    problems.append(
                        f"Текстура {zone_label} съедена на {var_loss:.0f}%: "
                        f"variance {sz.variance}→{oz.variance}. "
                        f"Причина: levels factor + ceiling clip выжигают детали."
                    )

            # Упёрлись в ceiling
            if oz.max_val >= ceiling - 2:
                zone_label = "лица" if lo == ZONE_BRIGHT[0] else "воротника"
                problems.append(
                    f"Зона {zone_label} упирается в ceiling={ceiling}: "
                    f"max={oz.max_val}. "
                    f"p95={oz.p95} — горячие пиксели на пределе."
                )

        # Потеря уникальных значений (плоская текстура)
        for lo, hi in [ZONE_DARK, ZONE_MID, ZONE_BRIGHT, ZONE_HOT]:
            oz = self.output_zones.get((lo, hi))
            if not oz or oz.count < 10000:
                continue
            if oz.n_unique < 30:
                label = _zone_name(lo, hi)
                problems.append(
                    f"Зона «{label}»: {oz.count} px содержат всего {oz.n_unique} "
                    f"уникальных значений ({oz.count//max(oz.n_unique,1)} px на значение) — "
                    f"текстура плоская, сплошное плато."
                )

        # Сравнение p95 shift
        for lo, hi in [ZONE_BRIGHT]:
            sz = self.source_zones.get((lo, hi))
            oz = self.output_zones.get((lo, hi))
            if sz and oz and sz.p95 > 0:
                p95_shift = oz.p95 - sz.p95
                if p95_shift > 20:
                    problems.append(
                        f"p95 лица сдвинулся на +{p95_shift:.0f} ({sz.p95}→{oz.p95}). "
                        f"Levels factor слишком агрессивный — горячие пиксели летят в ceiling."
                    )
                elif p95_shift < -30:
                    problems.append(
                        f"p95 лица упал на {p95_shift:.0f} ({sz.p95}→{oz.p95}). "
                        f"Face correction затемнил лицо слишком сильно."
                    )

        if not problems:
            problems.append("Всё чисто.")
        return problems

    def to_dict(self) -> dict:
        d = {"meta": {
            "source": self.source_path,
            "output": self.output_path,
            "machine_type": self.machine_type,
            "white_ceiling": self.white_ceiling,
        }}
        for tag, zones in [("source", self.source_zones), ("output", self.output_zones)]:
            d[tag] = {}
            for (lo, hi), z in zones.items():
                key = f"{lo}-{hi}"
                d[tag][key] = {k: v for k, v in asdict(z).items() if k != "name"}
                d[tag][key]["name"] = z.name
        return d

    def save_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def generate_report(source_path: str, output_path: str,
                    machine_type: str = "laser_standard",
                    face_mask_path: Optional[str] = None,
                    subject_mask_path: Optional[str] = None,
                    json_path: Optional[str] = None,
                    heatmap_path: Optional[str] = None,
                    txt_path: Optional[str] = None) -> PixelReport:
    report = PixelReport(
        source_path=source_path,
        output_path=output_path,
        machine_type=machine_type,
    )
    report.run()
    text = report.summary_text()
    print(text)
    if json_path:
        report.save_json(json_path)
    if txt_path:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
    return report
