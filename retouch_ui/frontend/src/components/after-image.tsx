/** Result preview with overlays (vignette, face oval). Uses useRenderMetrics for overlay positioning. */

import { useRef } from "react";
import { useRenderMetrics } from "../hooks/use-render-metrics";
import { VignetteOverlay } from "./vignette-overlay";
import { FaceOvalOverlay } from "./face-oval-overlay";
import type { VignetteParams } from "../lib/vignette-geometry";
import type { FaceOvalParams } from "../lib/face-oval-geometry";

interface Props {
  imageUrl: string | null;
  stepLabel: string;
  vignetteOverlayEnabled: boolean;
  faceOvalOverlayEnabled: boolean;
  faceOval: FaceOvalParams | null;
  onFaceOvalChange: (params: FaceOvalParams) => void;
  imageWidth: number;
  imageHeight: number;
  vignetteParams: VignetteParams;
  onVignetteParamChange: (path: string[], value: number) => void;
}

export function AfterImage({
  imageUrl,
  stepLabel,
  vignetteOverlayEnabled,
  faceOvalOverlayEnabled,
  faceOval,
  onFaceOvalChange,
  imageWidth,
  imageHeight,
  vignetteParams,
  onVignetteParamChange,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const { renderedWidth, renderedHeight, offsetX, offsetY, onImgLoad } = useRenderMetrics(containerRef, imgRef);

  const showVignetteOverlay =
    vignetteOverlayEnabled &&
    imageWidth > 0 &&
    imageHeight > 0;

  const showFaceOvalOverlay =
    faceOvalOverlayEnabled &&
    imageWidth > 0 &&
    imageHeight > 0 &&
    faceOval !== null;

  return (
    <div className="flex-1 flex flex-col">
      <h3 className="text-text-secondary text-sm mb-1 font-heading font-semibold">
        После: {stepLabel}
      </h3>
      <div
        ref={containerRef}
        className="bg-bg-secondary rounded-lg overflow-visible flex items-center justify-center min-h-[200px] relative"
      >
        {imageUrl ? (
          <img
            ref={imgRef}
            src={imageUrl}
            alt={`Step: ${stepLabel}`}
            className="max-h-[min(70vh,600px)] object-contain"
            onLoad={onImgLoad}
          />
        ) : (
          <span className="text-text-muted text-sm">Нет данных</span>
        )}
        {showVignetteOverlay && (
          <VignetteOverlay
            imageWidth={imageWidth}
            imageHeight={imageHeight}
            renderedWidth={renderedWidth}
            renderedHeight={renderedHeight}
            offsetX={offsetX}
            offsetY={offsetY}
            vignetteParams={vignetteParams}
            onVignetteParamChange={onVignetteParamChange}
          />
        )}
        {showFaceOvalOverlay && faceOval && (
          <FaceOvalOverlay
            imageWidth={imageWidth}
            imageHeight={imageHeight}
            renderedWidth={renderedWidth}
            renderedHeight={renderedHeight}
            offsetX={offsetX}
            offsetY={offsetY}
            faceOval={faceOval}
            onFaceOvalChange={onFaceOvalChange}
          />
        )}
      </div>
    </div>
  );
}
