/**
 * FaceOvalOverlay — интерактивный овал зоны лица (E.1).
 *
 * SVG-эллипс с 5 drag handles (center, top, bottom, left, right).
 * Параметры: cx, cy, rx, ry (0–1 нормализованные).
 * Появляется автоматически с координатами из эвристики.
 * source: "heuristic" → "manual" при первом drag.
 *
 * По аналогии с VignetteOverlay.
 */

import { useState, useRef, useCallback, useEffect } from "react";
import {
  computeFaceOvalFromDrag,
} from "../lib/face-oval-geometry";
import type { FaceOvalHandleType } from "../lib/face-oval-geometry";
import type { FaceOvalParams } from "../lib/types";

interface Props {
  /** Размеры изображения в пикселях */
  imageWidth: number;
  imageHeight: number;
  /** Реальные размеры отрендеренного <img> в DOM */
  renderedWidth: number;
  renderedHeight: number;
  /** Offset от края контейнера до <img> */
  offsetX: number;
  offsetY: number;
  /** Текущие параметры овала */
  faceOval: FaceOvalParams;
  /** Callback при изменении овала */
  onFaceOvalChange: (params: FaceOvalParams) => void;
}

export function FaceOvalOverlay({
  imageWidth,
  imageHeight,
  renderedWidth,
  renderedHeight,
  offsetX,
  offsetY,
  faceOval,
  onFaceOvalChange,
}: Props) {
  const [dragging, setDragging] = useState<FaceOvalHandleType | null>(null);
  const [shiftHeld, setShiftHeld] = useState(false);

  // ─── Shift tracking ────────────────────────────────────────────────
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === "Shift") setShiftHeld(true); };
    const onKeyUp = (e: KeyboardEvent) => { if (e.key === "Shift") setShiftHeld(false); };
    const onBlur = () => setShiftHeld(false);
    const onPointerDown = (e: PointerEvent) => { setShiftHeld(e.getModifierState("Shift")); };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onBlur);
    window.addEventListener("pointerdown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("pointerdown", onPointerDown);
    };
  }, [setShiftHeld]);

  // ─── Координаты овала в пикселях изображения ──────────────────────
  const cxPx = faceOval.cx * imageWidth;
  const cyPx = faceOval.cy * imageHeight;
  const rxPx = faceOval.rx * imageWidth;
  const ryPx = faceOval.ry * imageHeight;

  // ─── SVG ↔ Image координаты ───────────────────────────────────────
  const lastPosRef = useRef<{ x: number; y: number } | null>(null);

  const handleDragStart = useCallback(
    (handle: FaceOvalHandleType, e: React.PointerEvent) => {
      e.stopPropagation();
      e.preventDefault();
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
      setDragging(handle);
      lastPosRef.current = { x: e.clientX, y: e.clientY };
    },
    [],
  );

  const handleDragMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging || !lastPosRef.current) return;

      const dx = (e.clientX - lastPosRef.current.x) / renderedWidth;
      const dy = (e.clientY - lastPosRef.current.y) / renderedHeight;
      lastPosRef.current = { x: e.clientX, y: e.clientY };

      const changes = computeFaceOvalFromDrag(dragging, { dx, dy }, faceOval, shiftHeld);
      onFaceOvalChange({ ...faceOval, ...changes });
    },
    [dragging, shiftHeld, faceOval, onFaceOvalChange, renderedWidth, renderedHeight],
  );

  const handleDragEnd = useCallback(() => {
    setDragging(null);
    lastPosRef.current = null;
  }, []);

  // ─── Render ────────────────────────────────────────────────────────
  if (renderedWidth === 0 || renderedHeight === 0) return null;

  return (
    <svg
      viewBox={`0 0 ${imageWidth} ${imageHeight}`}
      width={renderedWidth}
      height={renderedHeight}
      className="absolute pointer-events-none"
      style={{
        left: offsetX,
        top: offsetY,
      }}
      onPointerMove={handleDragMove}
      onPointerUp={handleDragEnd}
      onPointerLeave={handleDragEnd}
    >
      {/* ── Овал лица ── */}
      <ellipse
        cx={cxPx}
        cy={cyPx}
        rx={rxPx}
        ry={ryPx}
        fill="var(--color-overlay-face-fill)"
        stroke="var(--color-overlay-face-stroke)"
        strokeWidth={2}
        strokeDasharray="8 4"
      />

      {/* ── Label: источник ── */}
      <text
        x={cxPx}
        y={cyPx - ryPx - 12}
        fill="var(--color-overlay-face-stroke)"
        fontSize={10}
        textAnchor="middle"
        fontFamily="'JetBrains Mono', monospace"
        opacity={0.8}
      >
        {faceOval.source === "manual" ? "manual" : "auto"}
      </text>

      {/* ── Drag Handles ── */}
      {/* Center */}
      <OvalHandle
        x={cxPx}
        y={cyPx}
        active={dragging === "center"}
        cursor="move"
        label="center"
        onPointerDown={(e) => handleDragStart("center", e)}
      />

      {/* Top */}
      <OvalHandle
        x={cxPx}
        y={cyPx - ryPx}
        active={dragging === "top"}
        cursor="ns-resize"
        label="top"
        onPointerDown={(e) => handleDragStart("top", e)}
      />

      {/* Bottom */}
      <OvalHandle
        x={cxPx}
        y={cyPx + ryPx}
        active={dragging === "bottom"}
        cursor="ns-resize"
        label="bottom"
        onPointerDown={(e) => handleDragStart("bottom", e)}
      />

      {/* Left */}
      <OvalHandle
        x={cxPx - rxPx}
        y={cyPx}
        active={dragging === "left"}
        cursor="ew-resize"
        label="left"
        onPointerDown={(e) => handleDragStart("left", e)}
      />

      {/* Right */}
      <OvalHandle
        x={cxPx + rxPx}
        y={cyPx}
        active={dragging === "right"}
        cursor="ew-resize"
        label="right"
        onPointerDown={(e) => handleDragStart("right", e)}
      />
    </svg>
  );
}

// ─── OvalHandle sub-component ────────────────────────────────────────

interface OvalHandleProps {
  x: number;
  y: number;
  active: boolean;
  cursor: string;
  label: string;
  onPointerDown: (e: React.PointerEvent) => void;
}

function OvalHandle({ x, y, active, cursor, label, onPointerDown }: OvalHandleProps) {
  const RADIUS = 6;
  return (
    <g className="pointer-events-auto" style={{ cursor }}>
      <circle
        cx={x} cy={y} r={RADIUS + 6}
        fill="transparent"
        onPointerDown={onPointerDown}
      />
      <circle
        cx={x} cy={y} r={RADIUS}
        fill={active ? "var(--color-overlay-face-handle)" : "var(--color-overlay-face-stroke)"}
        stroke="white"
        strokeWidth={2}
        onPointerDown={onPointerDown}
      />
      {/* Label */}
      <text
        x={x} y={y - RADIUS - 6}
        fill="var(--color-overlay-face-stroke)"
        fontSize={9}
        textAnchor="middle"
        fontFamily="'JetBrains Mono', monospace"
        opacity={0.7}
      >
        {label}
      </text>
    </g>
  );
}
