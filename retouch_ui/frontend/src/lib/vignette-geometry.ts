/**
 * Утилита расчёта геометрии арховой виньетки.
 *
 * Формулы совпадают с retouch/processing/vignette.py — generate_arch_mask().
 * Используется для мгновенного SVG-оверлея (L1) и обратного расчёта из drag.
 */

export interface VignetteParams {
  vertical_offset: number;       // 0–0.3
  vertical_diameter: number;     // 0.2–0.8
  blur_radius: number;           // 10–120 px
  headroom: number;              // 0.2–1.0
  horizontal_oversize: number;   // 0–0.5
}

export interface EllipseGeometry {
  /** Центр эллипса по X (пиксели изображения) */
  cx: number;
  /** Центр эллипса по Y */
  cy: number;
  /** Горизонтальный радиус эллипса */
  rx: number;
  /** Вертикальный радиус эллипса */
  ry: number;
  /** Верхняя точка арки (пиксели) */
  archTopY: number;
  /** Нижняя точка арки / базовая линия (пиксели) */
  archBottomY: number;
  /** Горизонтальный оверсайз в пикселях */
  hOversizePx: number;
}

/** Ограничения параметров — из CONFIG_SCHEMA */
export const VIGNETTE_LIMITS = {
  vertical_offset: { min: 0, max: 0.3 },
  vertical_diameter: { min: 0.2, max: 0.8 },
  blur_radius: { min: 10, max: 120 },
  headroom: { min: 0.2, max: 1.0 },
  horizontal_oversize: { min: 0, max: 0.5 },
} as const;

/** Типы drag-handle */
export type DragHandleType = "top" | "bottom" | "left" | "right";

/**
 * Рассчитать геометрию эллипса по параметрам конфига.
 * Формулы идентичны vignette.py.
 */
export function computeEllipseGeometry(
  params: VignetteParams,
  imageWidth: number,
  imageHeight: number,
): EllipseGeometry {
  const vOffset = imageHeight * params.vertical_offset;
  const vDiameter = imageHeight * params.vertical_diameter;
  const headroom = imageHeight * params.headroom;
  const hOversize = imageWidth * params.horizontal_oversize;

  const archBottomY = imageHeight - vOffset;
  const archTopY = archBottomY - vDiameter - headroom;

  return {
    cx: imageWidth / 2,
    cy: (archTopY + archBottomY) / 2,
    rx: (imageWidth + 2 * hOversize) / 2,
    ry: (archBottomY - archTopY) / 2,
    archTopY,
    archBottomY,
    hOversizePx: hOversize,
  };
}

/**
 * Обратный расчёт: из позиции drag handle → частичные параметры конфига.
 *
 * Возвращает только изменившиеся параметры. Вызывающий обязан сделать merge.
 */
export function computeParamsFromDrag(
  handle: DragHandleType,
  newPosition: { x: number; y: number },
  imageWidth: number,
  imageHeight: number,
  currentParams: VignetteParams,
): Partial<VignetteParams> {
  const clamp = (val: number, min: number, max: number) =>
    Math.min(max, Math.max(min, val));

  switch (handle) {
    case "top": {
      // Drag верхней точки арки — приоритет: headroom
      // archTopY = archBottomY - vDiameter - headroom
      // => headroom = (archBottomY - vDiameter - archTopY) / imageHeight
      const archBottomY = imageHeight - imageHeight * currentParams.vertical_offset;
      const vDiameter = imageHeight * currentParams.vertical_diameter;
      const headroom = (archBottomY - vDiameter - newPosition.y) / imageHeight;
      return {
        headroom: clamp(headroom, VIGNETTE_LIMITS.headroom.min, VIGNETTE_LIMITS.headroom.max),
      };
    }

    case "bottom": {
      // Drag нижней точки — vertical_offset
      // archBottomY = imageHeight - vOffset
      // => vertical_offset = (imageHeight - archBottomY) / imageHeight
      const verticalOffset = (imageHeight - newPosition.y) / imageHeight;
      return {
        vertical_offset: clamp(verticalOffset, VIGNETTE_LIMITS.vertical_offset.min, VIGNETTE_LIMITS.vertical_offset.max),
      };
    }

    case "left": {
      // Drag левого края — horizontal_oversize
      // Левый handle на x = -hOversize (за левым краем)
      // => hOversize = |newPosition.x|
      const hOversize = Math.abs(newPosition.x);
      return {
        horizontal_oversize: clamp(
          hOversize / imageWidth,
          VIGNETTE_LIMITS.horizontal_oversize.min,
          VIGNETTE_LIMITS.horizontal_oversize.max,
        ),
      };
    }

    case "right": {
      // Drag правого края — horizontal_oversize
      // Правый handle на x = imageWidth + hOversize
      // => hOversize = newPosition.x - imageWidth
      const hOversize = newPosition.x - imageWidth;
      return {
        horizontal_oversize: clamp(
          Math.max(0, hOversize) / imageWidth,
          VIGNETTE_LIMITS.horizontal_oversize.min,
          VIGNETTE_LIMITS.horizontal_oversize.max,
        ),
      };
    }

    default:
      return {};
  }
}

/**
 * Shift+drag верхней точки — меняет vertical_diameter вместо headroom.
 */
export function computeParamsFromTopDragShift(
  newPosition: { x: number; y: number },
  imageWidth: number,
  imageHeight: number,
  currentParams: VignetteParams,
): Partial<VignetteParams> {
  const clamp = (val: number, min: number, max: number) =>
    Math.min(max, Math.max(min, val));

  // archTopY = archBottomY - vDiameter - headroom
  // => vDiameter = archBottomY - headroom - archTopY
  const archBottomY = imageHeight - imageHeight * currentParams.vertical_offset;
  const headroom = imageHeight * currentParams.headroom;
  const vDiameter = (archBottomY - headroom - newPosition.y) / imageHeight;
  return {
    vertical_diameter: clamp(vDiameter, VIGNETTE_LIMITS.vertical_diameter.min, VIGNETTE_LIMITS.vertical_diameter.max),
  };
}

/**
 * Рассчитать offset и scale для наложения SVG на object-contain <img>.
 *
 * object-contain масштабирует изображение с сохранением пропорций и центрирует.
 * Эта функция вычисляет renderedWidth/renderedHeight и offset внутри контейнера.
 */
export function computeImgRenderMetrics(
  naturalWidth: number,
  naturalHeight: number,
  containerWidth: number,
  containerHeight: number,
) {
  const scale = Math.min(
    containerWidth / naturalWidth,
    containerHeight / naturalHeight,
  );
  const renderedWidth = naturalWidth * scale;
  const renderedHeight = naturalHeight * scale;
  return {
    offsetX: (containerWidth - renderedWidth) / 2,
    offsetY: (containerHeight - renderedHeight) / 2,
    renderedWidth,
    renderedHeight,
    scale,
  };
}
