"""PipelineContext и PipelineResult — вынесены для избежания круговых импортов."""

import logging
from dataclasses import dataclass, field

from PIL import Image

from retouch.processing.analysis.metrics import StepMetricsRecord
from retouch.processing.core.gates import GateState
from retouch.processing.core.plan import PipelinePlan, ValidatedPlan
from retouch.processing.analysis.zones import ZoneMasks

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PipelineContext — внутренняя упаковка (B.1)
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """Внутренний контекст пайплайна — упаковка параметров.

    НЕ передаётся в функции обработки — они сохраняют текущие сигнатуры.
    Используется только внутри pipeline.py для уменьшения количества
    аргументов, пробрасываемых между шагами.

    Примечание: img_chromakey добавлено сверх плана (B.1) — оно нужно
    для передачи результата хромакея в PipelineResult без дополнительного
    возврата из _run_pipeline_steps(). Практичное дополнение, не ломает
    обратную совместимость.
    """
    img_gray: Image.Image
    img_chromakey: Image.Image | None = None
    subject_mask: Image.Image | None = None
    face_mask: Image.Image | None = None
    hair_mask: Image.Image | None = None
    hair_anomaly: bool = False
    hair_ratio: float = 0.0
    face_oval: dict[str, float] | None = None
    analytics: dict | None = None
    machine_type: str = "laser_standard"
    config: dict = field(default_factory=dict)
    machine_cfg: dict = field(default_factory=dict)
    stone_type: str = "granite"
    step_mm: float = 0.300
    face_brightness_before: float = 0.0
    face_brightness_after: float = 0.0
    correction_factor: float = 1.0
    face_brightness_delta: float = 0.0
    warnings: list[str] = field(default_factory=list)
    debug_dir: str | None = None


# ---------------------------------------------------------------------------
# PipelineResult + consistency helpers
# ---------------------------------------------------------------------------


def _run_consistency_check(
    passed_oval: dict | None,
    result_oval: dict | None,
    warnings: list[str],
) -> None:
    """Проверить расхождение face_oval > 2% между переданным и результатом.

    Добавляет warning в список если расхождение > 0.02 по любому ключу.
    Используется в process_steps для consistency check preview → export.
    """
    if passed_oval is None or result_oval is None:
        return
    warn_keys = []
    for key in ("cx", "cy", "rx", "ry"):
        if key in passed_oval and key in result_oval:
            diff = abs(passed_oval[key] - result_oval[key])
            if diff > 0.02:
                warn_keys.append(f"{key}: {diff:.3f}")
    if warn_keys:
        msg = (
            f"consistency_mismatch: face_oval расхождение >2%: "
            f"{', '.join(warn_keys)}"
        )
        warnings.append(msg)
        logger.warning(msg)


@dataclass
class PipelineResult:
    """Результат пайплайна — все промежуточные этапы + диагностика."""

    # Промежуточные изображения (PIL.Image | None после release_intermediates)
    img_chromakey: Image.Image | None       # После хромакея (RGBA)
    img_gray: Image.Image | None            # После конвертации в L
    img_glow: Image.Image | None            # После Glow (L)
    img_leveled: Image.Image | None         # После Levels (L)
    img_face_corrected: Image.Image | None  # После face brightness correction (L)
    img_postproc: Image.Image | None        # После unsharp + shadow_noise + gamma (L)
    img_final: Image.Image                  # После виньетки (L) — всегда сохраняется
    arch_mask: Image.Image | None           # Маска виньетки (L)
    subject_mask: Image.Image | None        # Маска субъекта (L)
    face_mask: Image.Image | None           # Маска лица (L) — из face_region
    hair_mask: Image.Image | None           # Маска волос (L) — approximate

    # Диагностика
    glow_size: int
    glow_opacity: float
    face_brightness_before: float
    face_brightness_after: float
    face_correction_factor: float
    face_brightness_delta: float
    black_ratio: float
    blue_ratio: float
    width: int
    height: int
    analytics: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # F.2: Метрики качества
    clipped_pixels_pct: float = 0.0
    shadow_crush_pct: float = 0.0
    tonal_range_output: float = 0.0
    quality_warnings: list[str] = field(default_factory=list)
    # AUDIT-3.1: Параметры овала лица для передачи preview → export
    face_oval: dict | None = None
    # Step metrics: метрики после каждого шага
    step_metrics: list[StepMetricsRecord] = field(default_factory=list)
    # Pipeline plan: план обработки
    plan: PipelinePlan | None = None
    # Validated plan: валидированный план
    validated_plan: ValidatedPlan | None = None
    # Zone masks: зональные маски
    zone_masks: ZoneMasks | None = None
    # Hair diagnostics
    hair_anomaly: bool = False
    hair_ratio: float = 0.0
    # Gate state: состояние quality gates
    gate_state: GateState | None = None

    def release_intermediates(self):
        """Освободить память от промежуточных изображений.

        После вызова доступ к img_chromakey, img_gray, img_glow, img_leveled,
        img_face_corrected, img_postproc, arch_mask, subject_mask, face_mask
        вернёт None. img_final остаётся доступным — он нужен для сохранения.
        """
        self.img_chromakey = None
        self.img_gray = None
        self.img_glow = None
        self.img_leveled = None
        self.img_face_corrected = None
        self.img_postproc = None
        self.arch_mask = None
        self.subject_mask = None
        self.face_mask = None

    def __enter__(self):
        """Контекстный менеджер: автоматическое освобождение при выходе."""
        return self

    def __exit__(self, *exc):
        """Освободить промежуточные при выходе из with-блока."""
        self.release_intermediates()

    # ─── Deprecated attribute access ──────────────────────────────────

    def __getattr__(self, name):
        """Deprecated attributes: img_sharpened → img_postproc."""
        import warnings as _w
        if name == "img_sharpened":
            _w.warn(
                "PipelineResult.img_sharpened is deprecated, use img_postproc instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return self.img_postproc
        raise AttributeError(f"'PipelineResult' object has no attribute {name!r}")

    def __setattr__(self, name, value):
        """Deprecated attributes: img_sharpened → img_postproc."""
        if name == "img_sharpened":
            import warnings as _w
            _w.warn(
                "PipelineResult.img_sharpened is deprecated, use img_postproc instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            super().__setattr__("img_postproc", value)
        else:
            super().__setattr__(name, value)
