/**
 * VignetteOverlay — визуальный контроль формы арховой виньетки.
 *
 * L1 (мгновенный): SVG-эллипс + control points + dashed oversize.
 * L2 (отложенный): серверная размытая маска с GaussianBlur.
 *
 * Рендерится поверх результата в BeforeAfter.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import {
  computeEllipseGeometry,
  computeParamsFromDrag,
  computeParamsFromTopDragShift,
} from "../lib/vignette-geometry";
import type { VignetteParams, EllipseGeometry, DragHandleType } from "../lib/vignette-geometry";
import { fetchVignetteMask } from "../lib/api";

interface Props {
  /** Размеры изображения в пикселях (из PreviewDiagnostics) */
  imageWidth: number;
  imageHeight: number;
  /** Реальные размеры отрендеренного <img> в DOM */
  renderedWidth: number;
  renderedHeight: number;
  /** Offset от края контейнера до <img> (object-contain centering) */
  offsetX: number;
  offsetY: number;
  /** Текущие параметры виньетки из config */
  vignetteParams: VignetteParams;
  /** Callback при изменении параметра через drag */
  onVignetteParamChange: (path: string[], value: number) => void;
}

export function VignetteOverlay({
  imageWidth,
  imageHeight,
  renderedWidth,
  renderedHeight,
  offsetX,
  offsetY,
  vignetteParams,
  onVignetteParamChange,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [dragging, setDragging] = useState<DragHandleType | null>(null);
  const [shiftHeld, setShiftHeld] = useState(false);

  // L2: серверная маска
  const [serverMaskUrl, setServerMaskUrl] = useState<string | null>(null);
  const maskTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const maskAbortRef = useRef<AbortController | null>(null);

  // Геометрия эллипса
  const geo: EllipseGeometry = computeEllipseGeometry(vignetteParams, imageWidth, imageHeight);

  // Oversize padding для viewBox
  const viewboxPadding = Math.max(geo.hOversizePx + 30, 50);

  // ─── Shift tracking ────────────────────────────────────────────────
  useEffect(() => {
    const onDown = (e: KeyboardEvent) => { if (e.key === "Shift") setShiftHeld(true); };
    const onUp = (e: KeyboardEvent) => { if (e.key === "Shift") setShiftHeld(false); };
    window.addEventListener("keydown", onDown);
    window.addEventListener("keyup", onUp);
    return () => {
      window.removeEventListener("keydown", onDown);
      window.removeEventListener("keyup", onUp);
    };
  }, []);

  // ─── L2: Debounced server mask ─────────────────────────────────────
  useEffect(() => {
    // Отменить предыдущий запрос
    if (maskAbortRef.current) maskAbortRef.current.abort();
    if (maskTimerRef.current) clearTimeout(maskTimerRef.current);

    maskTimerRef.current = setTimeout(async () => {
      const controller = new AbortController();
      maskAbortRef.current = controller;
      try {
        const result = await fetchVignetteMask(
          imageWidth,
          imageHeight,
          vignetteParams,
          controller.signal,
        );
        if (!controller.signal.aborted) {
          setServerMaskUrl(result.mask);
        }
      } catch {
        // aborted или ошибка — L1-контур всё равно виден
      }
    }, 500);

    return () => {
      if (maskTimerRef.current) clearTimeout(maskTimerRef.current);
      if (maskAbortRef.current) maskAbortRef.current.abort();
    };
  }, [vignetteParams, imageWidth, imageHeight]);

  // ─── Drag logic ────────────────────────────────────────────────────
  const svgToImgCoords = useCallback(
    (clientX: number, clientY: number): { x: number; y: number } | null => {
      if (!svgRef.current) return null;
      const rect = svgRef.current.getBoundingClientRect();
      // SVG viewBox может быть шире изображения (oversize padding)
      const vbX = -viewboxPadding;
      const vbY = -10;
      const vbW = imageWidth + 2 * viewboxPadding;
      const vbH = imageHeight + 20;
      const scaleX = vbW / rect.width;
      const scaleY = vbH / rect.height;
      return {
        x: (clientX - rect.left) * scaleX + vbX,
        y: (clientY - rect.top) * scaleY + vbY,
      };
    },
    [imageWidth, imageHeight, viewboxPadding],
  );

  const handleDragStart = useCallback(
    (handle: DragHandleType, e: React.PointerEvent) => {
      e.stopPropagation();
      e.preventDefault();
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
      setDragging(handle);
    },
    [],
  );

  const handleDragMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging) return;
      const pos = svgToImgCoords(e.clientX, e.clientY);
      if (!pos) return;

      let changes: Partial<VignetteParams>;
      if (dragging === "top" && shiftHeld) {
        changes = computeParamsFromTopDragShift(pos, imageHeight, vignetteParams);
      } else {
        changes = computeParamsFromDrag(dragging, pos, imageWidth, imageHeight, vignetteParams);
      }

      // Применить изменения через callback
      for (const [key, value] of Object.entries(changes)) {
        onVignetteParamChange(["vignette", key], value as number);
      }
    },
    [dragging, shiftHeld, svgToImgCoords, imageWidth, imageHeight, vignetteParams, onVignetteParamChange],
  );

  const handleDragEnd = useCallback(() => {
    setDragging(null);
  }, []);

  // ─── Render ────────────────────────────────────────────────────────
  if (renderedWidth === 0 || renderedHeight === 0) return null;

  // SVG dimensions must match viewBox aspect ratio to prevent distortion.
  // viewBox is wider than the image (oversize padding), so the SVG element
  // must be proportionally wider than the rendered image.
  const svgScale = renderedWidth / imageWidth; // = renderedHeight / imageHeight
  const svgWidth = (imageWidth + 2 * viewboxPadding) * svgScale;
  const svgHeight = (imageHeight + 20) * svgScale;
  const svgLeft = offsetX - viewboxPadding * svgScale;
  const svgTop = offsetY - 10 * svgScale;

  return (
    <svg
      ref={svgRef}
      viewBox={`${-viewboxPadding} ${-10} ${imageWidth + 2 * viewboxPadding} ${imageHeight + 20}`}
      width={svgWidth}
      height={svgHeight}
      className="absolute pointer-events-none"
      style={{
        left: svgLeft,
        top: svgTop,
      }}
      onPointerMove={handleDragMove}
      onPointerUp={handleDragEnd}
      onPointerLeave={handleDragEnd}
    >
      {/* ── Oversize zone: затемнённые области за краями изображения ── */}
      {geo.hOversizePx > 5 && (
        <>
          <rect
            x={-viewboxPadding} y={0}
            width={viewboxPadding - 1} height={imageHeight}
            fill="var(--color-overlay-vignette-oversize)"
          />
          <rect
            x={imageWidth + 1} y={0}
            width={viewboxPadding - 1} height={imageHeight}
            fill="var(--color-overlay-vignette-oversize)"
          />
        </>
      )}

      {/* ── Рамка изображения ── */}
      <rect
        x={0} y={0} width={imageWidth} height={imageHeight}
        fill="none" stroke="var(--color-overlay-vignette-border)" strokeWidth={1}
      />

      {/* ── L2: серверная маска (полупрозрачная) ── */}
      {serverMaskUrl && (
        <image
          href={serverMaskUrl}
          x={0} y={0}
          width={imageWidth} height={imageHeight}
          opacity={0.2}
        />
      )}

      {/* ── L1: Эллипс-контур ── */}
      <ellipse
        cx={geo.cx}
        cy={geo.cy}
        rx={geo.rx}
        ry={geo.ry}
        fill="var(--color-overlay-vignette-fill)"
        stroke="var(--color-overlay-vignette-stroke)"
        strokeWidth={2}
        strokeDasharray={serverMaskUrl ? "none" : "8 4"}
      />

      {/* ── Базовая линия арки (archBottomY) ── */}
      <line
        x1={0} y1={geo.archBottomY}
        x2={imageWidth} y2={geo.archBottomY}
        stroke="var(--color-overlay-vignette-stroke)" strokeWidth={1}
        strokeDasharray="6 4" opacity={0.4}
      />

      {/* ── Oversize пунктирные линии ── */}
      {geo.hOversizePx > 5 && (
        <>
          {/* Левая сторона: от края к точке пересечения эллипса */}
          <line
            x1={0} y1={geo.archBottomY}
            x2={-geo.hOversizePx} y2={geo.cy}
            stroke="var(--color-overlay-vignette-stroke)" strokeWidth={1.5}
            strokeDasharray="4 3" opacity={0.5}
          />
          <line
            x1={-geo.hOversizePx} y1={geo.cy}
            x2={0} y2={geo.archTopY + (geo.archBottomY - geo.archTopY) * 0.1}
            stroke="var(--color-overlay-vignette-stroke)" strokeWidth={1.5}
            strokeDasharray="4 3" opacity={0.5}
          />
          {/* Правая сторона */}
          <line
            x1={imageWidth} y1={geo.archBottomY}
            x2={imageWidth + geo.hOversizePx} y2={geo.cy}
            stroke="var(--color-overlay-vignette-stroke)" strokeWidth={1.5}
            strokeDasharray="4 3" opacity={0.5}
          />
          <line
            x1={imageWidth + geo.hOversizePx} y1={geo.cy}
            x2={imageWidth} y2={geo.archTopY + (geo.archBottomY - geo.archTopY) * 0.1}
            stroke="var(--color-overlay-vignette-stroke)" strokeWidth={1.5}
            strokeDasharray="4 3" opacity={0.5}
          />
          {/* Подписи oversize */}
          <text
            x={-geo.hOversizePx / 2} y={geo.cy - 8}
            fill="var(--color-overlay-vignette-stroke)" fontSize={10} textAnchor="middle"
            fontFamily="'JetBrains Mono', monospace"
          >
            {(vignetteParams.horizontal_oversize * 100).toFixed(0)}%
          </text>
          <text
            x={imageWidth + geo.hOversizePx / 2} y={geo.cy - 8}
            fill="var(--color-overlay-vignette-stroke)" fontSize={10} textAnchor="middle"
            fontFamily="'JetBrains Mono', monospace"
          >
            {(vignetteParams.horizontal_oversize * 100).toFixed(0)}%
          </text>
        </>
      )}

      {/* ── Control Points (drag handles) ── */}
      {/* Top handle — headroom / vertical_diameter */}
      <DragHandle
        x={geo.cx}
        y={geo.archTopY}
        active={dragging === "top"}
        cursor="ns-resize"
        label={shiftHeld ? "diameter" : "headroom"}
        onPointerDown={(e) => handleDragStart("top", e)}
      />

      {/* Bottom handle — vertical_offset */}
      <DragHandle
        x={geo.cx}
        y={geo.archBottomY}
        active={dragging === "bottom"}
        cursor="ns-resize"
        label="offset"
        onPointerDown={(e) => handleDragStart("bottom", e)}
      />

      {/* Left handle — horizontal_oversize */}
      <DragHandle
        x={-geo.hOversizePx}
        y={geo.cy}
        active={dragging === "left"}
        cursor="ew-resize"
        label="oversize"
        onPointerDown={(e) => handleDragStart("left", e)}
      />

      {/* Right handle — horizontal_oversize */}
      <DragHandle
        x={imageWidth + geo.hOversizePx}
        y={geo.cy}
        active={dragging === "right"}
        cursor="ew-resize"
        label="oversize"
        onPointerDown={(e) => handleDragStart("right", e)}
      />
    </svg>
  );
}

// ─── DragHandle sub-component ────────────────────────────────────────

interface DragHandleProps {
  x: number;
  y: number;
  active: boolean;
  cursor: string;
  label: string;
  onPointerDown: (e: React.PointerEvent) => void;
}

function DragHandle({ x, y, active, cursor, label, onPointerDown }: DragHandleProps) {
  const RADIUS = 7;
  return (
    <g className="pointer-events-auto" style={{ cursor }}>
      {/* Invisible hit area */}
      <circle
        cx={x} cy={y} r={RADIUS + 6}
        fill="transparent"
        onPointerDown={onPointerDown}
      />
      {/* Visible handle */}
      <circle
        cx={x} cy={y} r={RADIUS}
        fill={active ? "var(--color-overlay-vignette-handle)" : "var(--color-overlay-vignette-stroke)"}
        stroke="white"
        strokeWidth={2}
        onPointerDown={onPointerDown}
      />
      {/* Label */}
      <text
        x={x} y={y - RADIUS - 6}
        fill="var(--color-overlay-vignette-stroke)"
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
