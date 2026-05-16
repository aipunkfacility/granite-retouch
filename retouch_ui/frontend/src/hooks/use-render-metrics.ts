import { useCallback, useEffect, useState, type RefObject } from "react";
import { computeImgRenderMetrics } from "../lib/vignette-geometry";

export interface RenderMetrics {
  renderedWidth: number;
  renderedHeight: number;
  offsetX: number;
  offsetY: number;
}

export function useRenderMetrics(
  containerRef: RefObject<HTMLDivElement | null>,
  imgRef: RefObject<HTMLImageElement | null>,
): RenderMetrics & { onImgLoad: () => void } {
  const [metrics, setMetrics] = useState<RenderMetrics>({
    renderedWidth: 0,
    renderedHeight: 0,
    offsetX: 0,
    offsetY: 0,
  });

  const updateMetrics = useCallback(() => {
    const container = containerRef.current;
    const img = imgRef.current;
    if (!container || !img || !img.naturalWidth || !img.naturalHeight) return;

    const containerRect = container.getBoundingClientRect();
    const m = computeImgRenderMetrics(
      img.naturalWidth,
      img.naturalHeight,
      containerRect.width,
      containerRect.height,
    );
    setMetrics(m);
  }, [containerRef, imgRef]);

  const onImgLoad = useCallback(() => {
    requestAnimationFrame(updateMetrics);
  }, [updateMetrics]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver(() => {
      updateMetrics();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [containerRef, updateMetrics]);

  return { ...metrics, onImgLoad };
}
