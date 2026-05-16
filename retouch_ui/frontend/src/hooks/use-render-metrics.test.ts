import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useRef } from "react";
import { useRenderMetrics } from "./use-render-metrics";

describe("useRenderMetrics", () => {
  it("returns zero metrics when refs are empty", () => {
    const { result } = renderHook(() => {
      const containerRef = useRef<HTMLDivElement>(null);
      const imgRef = useRef<HTMLImageElement>(null);
      return useRenderMetrics(containerRef, imgRef);
    });

    expect(result.current.renderedWidth).toBe(0);
    expect(result.current.renderedHeight).toBe(0);
    expect(result.current.offsetX).toBe(0);
    expect(result.current.offsetY).toBe(0);
  });

  it("onImgLoad is a function", () => {
    const { result } = renderHook(() => {
      const containerRef = useRef<HTMLDivElement>(null);
      const imgRef = useRef<HTMLImageElement>(null);
      return useRenderMetrics(containerRef, imgRef);
    });

    expect(typeof result.current.onImgLoad).toBe("function");
  });

  it("returns stable references across renders", () => {
    const { result, rerender } = renderHook(() => {
      const containerRef = useRef<HTMLDivElement>(null);
      const imgRef = useRef<HTMLImageElement>(null);
      return useRenderMetrics(containerRef, imgRef);
    });

    const first = result.current.onImgLoad;
    rerender();
    expect(result.current.onImgLoad).toBe(first);
  });
});
