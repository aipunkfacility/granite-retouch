/** Side-by-side before/after preview with step labels, vignette overlay, and face oval overlay */

import { useState, useRef, useCallback, useEffect } from "react";
import { VignetteOverlay } from "./vignette-overlay";
import { FaceOvalOverlay } from "./face-oval-overlay";
import { STEP_LABELS } from "./step-selector";
import { computeImgRenderMetrics } from "../lib/vignette-geometry";
import type { VignetteParams } from "../lib/vignette-geometry";
import type { FaceOvalParams } from "../lib/face-oval-geometry";

interface Props {
  originalUrl: string | null;
  images: Record<string, string>;
  selectedStep: string;
  onStepChange: (step: string) => void;
  /** Vignette overlay props (only when enabled and on "final" step) */
  vignetteOverlayEnabled: boolean;
  /** Face oval overlay props */
  faceOvalOverlayEnabled: boolean;
  faceOval: FaceOvalParams | null;
  onFaceOvalChange: (params: FaceOvalParams) => void;
  imageWidth: number;
  imageHeight: number;
  vignetteParams: VignetteParams;
  onVignetteParamChange: (path: string[], value: number) => void;
}

export function BeforeAfter({
  originalUrl,
  images,
  selectedStep,
  vignetteOverlayEnabled,
  faceOvalOverlayEnabled,
  faceOval,
  onFaceOvalChange,
  imageWidth,
  imageHeight,
  vignetteParams,
  onVignetteParamChange,
}: Props) {
  const stepLabel = STEP_LABELS[selectedStep] ?? selectedStep;
  const resultContainerRef = useRef<HTMLDivElement>(null);
  const resultImgRef = useRef<HTMLImageElement>(null);
  const [renderMetrics, setRenderMetrics] = useState({
    renderedWidth: 0,
    renderedHeight: 0,
    offsetX: 0,
    offsetY: 0,
  });

  // Recalculate rendered metrics when image loads or container resizes
  const updateMetrics = useCallback(() => {
    const container = resultContainerRef.current;
    const img = resultImgRef.current;
    if (!container || !img || !img.naturalWidth || !img.naturalHeight) return;

    const containerRect = container.getBoundingClientRect();
    const metrics = computeImgRenderMetrics(
      img.naturalWidth,
      img.naturalHeight,
      containerRect.width,
      containerRect.height,
    );
    setRenderMetrics(metrics);
  }, []);

  // Update on image load
  const handleImgLoad = useCallback(() => {
    // Small delay to ensure layout is settled
    requestAnimationFrame(updateMetrics);
  }, [updateMetrics]);

  // Update on container resize
  useEffect(() => {
    const container = resultContainerRef.current;
    if (!container) return;

    const observer = new ResizeObserver(() => {
      updateMetrics();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [updateMetrics]);

  // Show vignette overlay only on "final" step with overlay enabled
  const showVignetteOverlay =
    vignetteOverlayEnabled &&
    selectedStep === "final" &&
    imageWidth > 0 &&
    imageHeight > 0;

  // Show face oval overlay on "face_corrected" or "final" step
  const showFaceOvalOverlay =
    faceOvalOverlayEnabled &&
    (selectedStep === "face_corrected" || selectedStep === "final") &&
    imageWidth > 0 &&
    imageHeight > 0 &&
    faceOval !== null;

  return (
    <div className="flex gap-4 w-full">
      {/* Before */}
      <div className="flex-1 flex flex-col">
        <p className="text-text-secondary text-sm mb-1 font-heading font-semibold">До</p>
        <div className="bg-bg-secondary rounded-lg overflow-hidden flex items-center justify-center min-h-[200px]">
          {originalUrl ? (
            <img src={originalUrl} alt="Original" className="max-h-[min(70vh,600px)] object-contain" />
          ) : (
            <span className="text-text-muted text-sm">Нет изображения</span>
          )}
        </div>
      </div>
      {/* After */}
      <div className="flex-1 flex flex-col">
        <p className="text-text-secondary text-sm mb-1 font-heading font-semibold">
          После: {stepLabel}
        </p>
        <div
          ref={resultContainerRef}
          className="bg-bg-secondary rounded-lg overflow-visible flex items-center justify-center min-h-[200px] relative"
        >
          {images[selectedStep] ? (
            <img
              ref={resultImgRef}
              src={images[selectedStep]}
              alt={`Step: ${stepLabel}`}
              className="max-h-[min(70vh,600px)] object-contain"
              onLoad={handleImgLoad}
            />
          ) : (
            <span className="text-text-muted text-sm">Нет данных</span>
          )}
          {/* Vignette overlay */}
          {showVignetteOverlay && (
            <VignetteOverlay
              imageWidth={imageWidth}
              imageHeight={imageHeight}
              renderedWidth={renderMetrics.renderedWidth}
              renderedHeight={renderMetrics.renderedHeight}
              offsetX={renderMetrics.offsetX}
              offsetY={renderMetrics.offsetY}
              vignetteParams={vignetteParams}
              onVignetteParamChange={onVignetteParamChange}
            />
          )}
          {/* Face oval overlay */}
          {showFaceOvalOverlay && faceOval && (
            <FaceOvalOverlay
              imageWidth={imageWidth}
              imageHeight={imageHeight}
              renderedWidth={renderMetrics.renderedWidth}
              renderedHeight={renderMetrics.renderedHeight}
              offsetX={renderMetrics.offsetX}
              offsetY={renderMetrics.offsetY}
              faceOval={faceOval}
              onFaceOvalChange={onFaceOvalChange}
            />
          )}
        </div>
      </div>
    </div>
  );
}
