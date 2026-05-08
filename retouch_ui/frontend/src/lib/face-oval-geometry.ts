/**
 * face-oval-geometry.ts — геометрия овала зоны лица.
 *
 * Нормализованные координаты (0–1) для масштабонезависимости.
 */

export interface FaceOvalParams {
  cx: number;  // центр X (0–1)
  cy: number;  // центр Y (0–1)
  rx: number;  // радиус X (0–1)
  ry: number;  // радиус Y (0–1)
  source: "heuristic" | "manual" | "auto" | "heuristic_legacy";
}

export type FaceOvalHandleType = "top" | "bottom" | "left" | "right" | "center";

/** Ограничения для овала */
export const FACE_OVAL_LIMITS = {
  cx: { min: 0.05, max: 0.95 },
  cy: { min: 0.05, max: 0.70 },
  rx: { min: 0.03, max: 0.45 },
  ry: { min: 0.03, max: 0.45 },
};

/** Ограничить значение в пределах */
function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

/** Вычислить параметры овала из drag-смещения */
export function computeFaceOvalFromDrag(
  handle: FaceOvalHandleType,
  deltaNorm: { dx: number; dy: number },
  current: FaceOvalParams,
  shiftHeld: boolean,
): Partial<FaceOvalParams> {
  const L = FACE_OVAL_LIMITS;
  const changes: Partial<FaceOvalParams> = {};

  switch (handle) {
    case "center":
      changes.cx = clamp(current.cx + deltaNorm.dx, L.cx.min, L.cx.max);
      changes.cy = clamp(current.cy + deltaNorm.dy, L.cy.min, L.cy.max);
      break;
    case "top":
      changes.ry = clamp(current.ry - deltaNorm.dy, L.ry.min, L.ry.max);
      changes.cy = clamp(current.cy + deltaNorm.dy * 0.5, L.cy.min, L.cy.max);
      break;
    case "bottom":
      changes.ry = clamp(current.ry + deltaNorm.dy, L.ry.min, L.ry.max);
      changes.cy = clamp(current.cy + deltaNorm.dy * 0.5, L.cy.min, L.cy.max);
      break;
    case "left":
      changes.rx = clamp(current.rx - deltaNorm.dx, L.rx.min, L.rx.max);
      if (shiftHeld) {
        // Shift = пропорциональное изменение ry
        changes.ry = clamp(current.ry - deltaNorm.dx, L.ry.min, L.ry.max);
      }
      break;
    case "right":
      changes.rx = clamp(current.rx + deltaNorm.dx, L.rx.min, L.rx.max);
      if (shiftHeld) {
        changes.ry = clamp(current.ry + deltaNorm.dx, L.ry.min, L.ry.max);
      }
      break;
  }

  changes.source = "manual";
  return changes;
}
